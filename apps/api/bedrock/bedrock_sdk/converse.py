import asyncio
import copy
import inspect
import json
import logging
import re
import traceback
import typing
import uuid
from dataclasses import dataclass, fields
from dataclasses import field
from datetime import datetime
from functools import cached_property
from typing import Any, List, Dict, Optional, Union, get_origin, get_args, get_type_hints, Callable
from typing import Literal, ByteString
from zoneinfo import ZoneInfo

import boto3
import json5
import json_repair
from pydantic import BaseModel, ValidationError, Field
from .tools import tool as agent_tool, Tools
from .bases import BaseCallbackHandler

logger = logging.getLogger(__name__)


def _to_camel_case(snake_str: str) -> str:
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def _from_camel_case(camel_str: str) -> str:
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_str)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class InvalidFormat(ValueError):
    pass


@dataclass
class ToolRegistry:
    tools: Dict[str, Callable] = field(default_factory=dict)

    def register(self, tool):
        # Check if it's a Tools class instance
        if hasattr(tool, 'get_tools'):
            # Register all tools from the class
            registered_tools = []
            for class_tool in tool.get_tools():
                tool_name = class_tool._tool_spec['name']
                self.tools[tool_name] = class_tool
                registered_tools.append(class_tool)
            return registered_tools
        elif hasattr(tool, '_tool_spec'):
            tool_name = tool._tool_spec['name']
            self.tools[tool_name] = tool
            return tool
        else:
            raise ValueError(f"Object {tool} is not a valid tool (not decorated with @tool or not a Tools instance)")

    def execute(self, tool_name: str, arguments: dict) -> Any:
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found in registry")

        tool = self.tools[tool_name]
        if hasattr(tool, '_execute'):
            return tool._execute(**arguments)
        else:
            return tool(**arguments)

    def get_tool(self, tool_name: str) -> Optional[Callable]:
        return self.tools.get(tool_name)

    def list_tools(self) -> List[str]:
        return list(self.tools.keys())

    def clear(self):
        self.tools.clear()


class FromDictMixin:
    _FROM_DICT_EXCLUSIONS = []
    _FROM_DICT_SERIALIZATION_EXCLUSIONS = []

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        if data is None:
            return None
        type_hints = get_type_hints(cls)
        kwargs = {}
        data = {_from_camel_case(k): v for k, v in data.items()}
        for field_info in fields(cls):
            field_name = field_info.name
            if field_name in cls._FROM_DICT_EXCLUSIONS:
                continue
            if field_name not in data:
                continue
            value = data[field_name]
            field_type = type_hints.get(field_name, Any)
            if field_name in cls._FROM_DICT_SERIALIZATION_EXCLUSIONS:
                kwargs[field_name] = value
            else:
                kwargs[field_name] = cls._from_convert_value(value, field_type)
        return cls(**kwargs)

    @classmethod
    def _from_convert_value(cls, value: Any, field_type: Any) -> Any:
        if value is None:
            return None
        origin = get_origin(field_type)
        args = get_args(field_type)
        if origin is Union and type(None) in args:
            actual_type = next(arg for arg in args if arg is not type(None))
            return cls._from_convert_value(value, actual_type)
        elif origin is list or origin is List:
            item_type = args[0] if args else Any
            return [cls._from_convert_value(item, item_type) for item in value]
        elif origin is dict or origin is Dict:
            key_type, value_type = args if args else (Any, Any)
            return {cls._from_convert_value(k, key_type): cls._from_convert_value(v, value_type) for k, v in
                    value.items()}
        elif hasattr(field_type, 'from_dict'):
            return field_type.from_dict(value)
        else:
            return value


class ToDictMixin:
    _TO_DICT_EXCLUSIONS = []
    _TO_DICT_SERIALIZATION_EXCLUSIONS = []

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for class_field in fields(self):
            if class_field.name in self._TO_DICT_EXCLUSIONS:
                continue
            value = getattr(self, class_field.name)
            if value is None:
                continue
            camel_case_name = _to_camel_case(class_field.name)
            if class_field.name in self._TO_DICT_SERIALIZATION_EXCLUSIONS:
                result[camel_case_name] = value
            else:
                result[camel_case_name] = self._to_convert_value(value)
        return result

    def _to_convert_value(self, value: Any) -> Any:
        if hasattr(value, 'to_dict') and callable(value.to_dict):
            return value.to_dict()
        elif isinstance(value, list):
            return [self._to_convert_value(item) for item in value]
        elif isinstance(value, dict):
            return {_to_camel_case(k): self._to_convert_value(v) for k, v in value.items()}
        else:
            return value


@dataclass
class S3Location(ToDictMixin):
    uri: str
    bucket_owner: Optional[str] = None


@dataclass
class FileSource(ToDictMixin):
    bytes: ByteString


@dataclass
class Image(ToDictMixin):
    format: Literal["png", "jpeg", "gif", "webp"]
    source: FileSource

    def __post_init__(self):
        valid_formats = typing.get_args(self.__annotations__['format'])
        if self.format == 'jpg':
            self.format = 'jpeg'
        if self.format not in valid_formats:
            raise InvalidFormat(f"Invalid format: {self.format}. Must be one of: {', '.join(valid_formats)}")


@dataclass
class Document(ToDictMixin):
    format: Literal["pdf", "csv", "doc", "docx", "xls", "xlsx", "html", "txt", "md"]
    name: str
    source: FileSource

    def __post_init__(self):
        valid_formats = typing.get_args(self.__annotations__['format'])
        if self.format not in valid_formats:
            raise InvalidFormat(f"Invalid format: {self.format}. Must be one of: {', '.join(valid_formats)}")
        self.clean_name()

    def clean_name(self):
        self.name = self.name.encode('ascii', 'ignore').decode('ascii')
        self.name = re.sub(r'[^a-zA-Z0-9\s\-\(\)\[\]]', '', self.name)
        self.name = re.sub(r'\s{2,}', ' ', self.name)
        self.name = self.name.strip()


@dataclass
class VideoSource(ToDictMixin):
    bytes: Optional[ByteString] = None
    s3_location: Optional[S3Location] = None


@dataclass
class Video(ToDictMixin):
    format: Literal["mkv", "mov", "mp4", "webm", "flv", "mpeg", "mpg", "wmv", "three_gp"]
    source: VideoSource


@dataclass
class ToolUse(FromDictMixin, ToDictMixin):
    _FROM_DICT_SERIALIZATION_EXCLUSIONS = ['input']

    tool_use_id: str
    name: str
    input: Any  # Can be any JSON structure


@dataclass
class ToolResultContent(ToDictMixin, FromDictMixin):
    json: Optional[Any] = None
    text: Optional[str] = None
    image: Optional[Image] = None
    document: Optional[Document] = None
    video: Optional[Video] = None


@dataclass
class ToolResult(ToDictMixin, FromDictMixin):
    tool_use_id: str
    content: List[ToolResultContent]
    status: Literal["success", "error"]


@dataclass
class GuardContentText(ToDictMixin):
    text: str
    qualifiers: List[Literal["grounding_source", "query", "guard_content"]]


@dataclass
class GuardContent(ToDictMixin):
    text: Optional[GuardContentText] = None
    image: Optional[Image] = None


@dataclass
class CachePoint(ToDictMixin):
    type: Literal["default"] = "default"


@dataclass
class ReasoningText(ToDictMixin):
    text: str
    signature: str


@dataclass
class ReasoningContent(ToDictMixin):
    reasoning_text: ReasoningText
    redacted_content: ByteString


@dataclass
class SystemContent(ToDictMixin, FromDictMixin):
    text: Optional[str] = None
    guard_content: Optional[GuardContent] = None
    cache_point: Optional[CachePoint] = None


@dataclass
class ConverseInferenceConfig(ToDictMixin):
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stop_sequences: Optional[List[str]] = None


@dataclass
class ToolSpec(ToDictMixin):
    _TO_DICT_SERIALIZATION_EXCLUSIONS = ['input_schema']

    name: str
    description: str
    input_schema: Dict[Literal["json"], Any]

    @classmethod
    def from_pydantic(cls, pydantic_model):
        return cls(
            name=pydantic_model.__name__,
            description=f"Output data in the format of {pydantic_model.__name__}",
            input_schema={"json": pydantic_model.model_json_schema()}
        )

    @classmethod
    def from_function(cls, func):
        if hasattr(func, '_tool_spec'):
            spec = func._tool_spec
            return cls(
                name=spec["name"],
                description=spec["description"],
                input_schema=spec["input_schema"]
            )
        else:
            raise ValueError(f"Function {func.__name__} is not decorated with @tool")


@dataclass
class Tool(ToDictMixin):
    tool_spec: Optional[ToolSpec] = None
    cache_point: Optional[CachePoint] = None

    @classmethod
    def from_pydantic(cls, pydantic_model):
        return cls(tool_spec=ToolSpec.from_pydantic(pydantic_model))

    @classmethod
    def from_function(cls, func):
        return cls(tool_spec=ToolSpec.from_function(func))


@dataclass
class ToolChoiceAuto(ToDictMixin):
    pass


@dataclass
class ToolChoiceAny(ToDictMixin):
    pass


@dataclass
class ToolChoiceTool(ToDictMixin):
    name: str


@dataclass
class ToolChoice(ToDictMixin):
    auto: Optional[ToolChoiceAuto] = None
    any: Optional[ToolChoiceAny] = None
    tool: Optional[ToolChoiceTool] = None


@dataclass
class ConverseToolConfig(ToDictMixin):
    tools: List[Tool] = field(default_factory=list)
    tool_choice: Optional[ToolChoice] = None

    def add_cache_point(self):
        self.tools.append(Tool(cache_point=CachePoint()))


@dataclass
class ConverseGuardrailConfig(ToDictMixin):
    guardrail_identifier: str
    guardrail_version: str
    trace: Literal["enabled", "disabled", "enabled_full"] = "disabled"


@dataclass
class PromptVariable(ToDictMixin):
    text: str


@dataclass
class ConversePerformanceConfig(ToDictMixin):
    latency: Literal["standard", "optimized"] = "standard"


@dataclass
class MessageContent(ToDictMixin, FromDictMixin):
    text: Optional[str] = None
    image: Optional[Image] = None
    document: Optional[Document] = None
    video: Optional[Video] = None
    tool_use: Optional[ToolUse] = None
    tool_result: Optional[ToolResult] = None
    guard_content: Optional[GuardContent] = None
    cache_point: Optional[CachePoint] = None
    reasoning_content: Optional[ReasoningContent] = None

    def reduce_size(self):
        if self.text:
            self.text = self.text[:400000].replace('\n', ' ')


@dataclass
class Message(ToDictMixin, FromDictMixin):
    content: List[MessageContent] = field(default_factory=list)
    role: Literal["user", "assistant"] = 'user'

    def add_current_time(self, tz=ZoneInfo('UTC')):
        if isinstance(tz, str):
            tz = ZoneInfo(tz)
        self.add_text(f'<current_time>{datetime.now().astimezone(tz).isoformat()}</current_time>')

    def add_text(self, text, tag=None):
        if text and text.strip('\n').strip():
            if tag:
                text = f'<{tag}>{text}</{tag}>'
            self.content.append(MessageContent(text=text))
        return self

    def add_image(self, source, image_format, skip_on_invalid=False):
        if not skip_on_invalid:
            self.content.append(MessageContent(image=Image(source=FileSource(bytes=source), format=image_format)))
        else:
            try:
                self.content.append(MessageContent(image=Image(source=FileSource(bytes=source), format=image_format)))
            except InvalidFormat as e:
                logger.warning(f'Could not add image to prompt {image_format} is invalid: {e}')
        return self

    def add_cache_point(self):
        self.content.append(MessageContent(cache_point=CachePoint()))
        return self

    def get_document_names(self):
        return {content.document.name for content in self.content if content.document}

    def add_document(self, source, name, skip_on_invalid=False):
        split_name = name.split('.')
        document_format = split_name[-1].lower()
        name = '_'.join(split_name[:-1])
        document = Document(format=document_format, name=name, source=FileSource(bytes=source))
        if document.name in self.get_document_names():
            document.name += f'_{uuid.uuid4().hex[:6]}'
        if not skip_on_invalid:
            self.content.append(MessageContent(document=document))
        else:
            try:
                self.content.append(
                    MessageContent(
                        document=Document(format=document_format, name=name, source=FileSource(bytes=source))))
            except InvalidFormat as e:
                logger.warning(f'Could not add document to prompt {name} is invalid: {e}')
        return self

    def add_video(self, video):
        raise NotImplementedError

    def reduce_tokens(self):
        for content in self.content:
            if content.text:
                content.text = content.text.replace('\n', ' ').replace('\r', ' ')


@dataclass
class Prompt(Message):
    pass


@dataclass
class ConverseOutput(FromDictMixin):
    message: Optional[Message] = None


@dataclass
class TokenUsage(FromDictMixin):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0

    def __str__(self):
        return (f"input_tokens: {self.input_tokens}"
                f"\noutput_tokens: {self.output_tokens}"
                f"\ntotal_tokens: {self.total_tokens}"
                f"\ncache_read_input_tokens: {self.cache_read_input_tokens}"
                f"\ncache_write_input_tokens: {self.cache_write_input_tokens}")


@dataclass
class ConverseMetrics(FromDictMixin):
    latency_ms: int = 0


@dataclass
class GuardrailAssessment(FromDictMixin):
    topic_policy: Optional[Dict] = None
    content_policy: Optional[Dict] = None
    word_policy: Optional[Dict] = None
    sensitive_information_policy: Optional[Dict] = None
    contextual_grounding_policy: Optional[Dict] = None
    invocation_metrics: Optional[Dict] = None


@dataclass
class GuardrailTrace(FromDictMixin):
    model_output: Optional[List[str]] = None
    input_assessment: Optional[Dict[str, GuardrailAssessment]] = None
    output_assessments: Optional[Dict[str, List[GuardrailAssessment]]] = None
    action_reason: Optional[str] = None


@dataclass
class PromptRouterTrace(FromDictMixin):
    invoked_model_id: str


@dataclass
class ConverseTrace(FromDictMixin):
    guardrail: Optional[GuardrailTrace] = None
    prompt_router: Optional[PromptRouterTrace] = None


@dataclass
class ModelCost:
    model_name: str
    input: float = 0
    output: float = 0
    cached_write: float = 0
    cached_read: float = 0


@dataclass
class ConverseCost:
    usage: TokenUsage
    model_id: str

    MODELS = [
        ModelCost(model_name='claude-sonnet-4', input=0.003, output=0.015, cached_write=0.00375, cached_read=0.0003),
        ModelCost(model_name='claude-3-7-sonnet', input=0.003, output=0.015, cached_write=0.00375, cached_read=0.0003),
        ModelCost(model_name='claude-3-5-sonnet', input=0.003, output=0.015, cached_write=0.00375, cached_read=0.0003),
        ModelCost(model_name='claude-3-5-haiku', input=0.0008, output=0.004, cached_write=0.001, cached_read=0.00008),
        ModelCost(model_name='amazon.nova-pro', input=0.0008, output=0.0032),
        ModelCost(model_name='claude-3-haiku', input=0.00025, output=0.00125),
        ModelCost(model_name='amazon.nova-lite', input=0.00006, output=0.00024),
        ModelCost(model_name='gemini-2.0-flash-001', input=0.0001, output=0.0004),
        ModelCost(model_name='llama4-maverick', input=0.00024, output=0.00097),
    ]

    def __str__(self):
        return (f"input_cost: {self.input_cost}"
                f"\noutput_cost: {self.output_cost}"
                f"\ntotal_cost: {self.total_cost}"
                f"\ncached_read_cost: {self.cached_read_cost}"
                f"\ncached_read_cost: {self.cached_read_cost}")

    @cached_property
    def cost(self):
        for model_cost in self.MODELS:
            if model_cost.model_name in self.model_id.lower():
                return model_cost
        return ModelCost(model_name='unknown')

    @property
    def input_cost(self):
        return self.cost.input * self.usage.input_tokens / 1000

    @property
    def output_cost(self):
        return self.cost.output * self.usage.output_tokens / 1000

    @property
    def cached_write_cost(self):
        return self.cost.cached_write * self.usage.cache_write_input_tokens / 1000

    @property
    def cached_read_cost(self):
        return self.cost.cached_read * self.usage.cache_read_input_tokens / 1000

    @property
    def total_cost(self):
        return sum([self.input_cost, self.output_cost, self.cached_write_cost, self.cached_write_cost])


@dataclass
class ConverseResponse(FromDictMixin):
    output: Optional[ConverseOutput] = None
    stop_reason: Optional[str] = None
    usage: Optional[TokenUsage] = None
    metrics: Optional[ConverseMetrics] = None
    additional_model_response_fields: Optional[Any] = None
    trace: Optional[ConverseTrace] = None
    performance_config: Optional[ConversePerformanceConfig] = None
    response_metadata: Optional[Dict] = None
    model_id = None

    @property
    def content(self):
        return self.output.message.content[0].text

    @property
    def cost(self):
        return ConverseCost(model_id=self.model_id, usage=self.usage)


@dataclass
class Converse(ToDictMixin, FromDictMixin):
    model_id: str
    messages: List[Message] = field(default_factory=list)
    system: List[SystemContent] = field(default_factory=list)
    inference_config: Optional[ConverseInferenceConfig] = None
    tool_config: Optional[ConverseToolConfig] = None
    guardrail_config: Optional[ConverseGuardrailConfig] = None
    additional_model_request_fields: Optional[Any] = None
    prompt_variables: Optional[Dict[str, PromptVariable]] = None
    additional_model_response_field_paths: Optional[List[str]] = None
    request_metadata: Optional[Dict[str, str]] = None
    performance_config: Optional[ConversePerformanceConfig] = None
    _client: boto3.client = None
    region_name: str = None
    callbacks: List[BaseCallbackHandler] = field(default_factory=list)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    _async_client: boto3.client = None
    tool_registry: ToolRegistry = field(default_factory=ToolRegistry)

    _TO_DICT_EXCLUSIONS = ['region_name', '_client', 'callbacks', 'aws_access_key_id', 'aws_secret_access_key',
                           '_async_client', 'tool_registry']
    CACHE_SUPPORTED_MODELS = ['claude-3-5-haiku', 'claude-3-7-sonnet', 'amazon.nova', 'claude-sonnet-4',
                              'claude-opus-4']

    def add_message(self):
        message = Message()
        self.messages.append(message)
        return message

    @property
    def session(self):
        if self.aws_access_key_id and self.aws_secret_access_key:
            return boto3.Session(
                region_name=self.region_name,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
            )
        else:
            return boto3.Session(region_name=self.region_name)

    @property
    def client(self):
        if self._client is None:
            self._client = self.session.client('bedrock-runtime')
        return self._client

    def _format_invoke_message(self, message):
        if isinstance(message, str):
            message = Message().add_text(message)
        return self.messages + [message]

    def invoke(self, message: Message | str):
        response = self._get_response(self._format_invoke_message(message))
        return self.format_response(response)

    async def ainvoke(self, message: Message | str):
        response = await self._aget_response(self._format_invoke_message(message))
        return self.format_response(response)

    def format_response(self, response):
        return response

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def _get_response(self, messages=None):
        for callback in self.callbacks:
            callback.on_converse_start(self)
        self.remove_invalid_caching(messages)
        payload = self.to_dict()
        if messages:
            payload['messages'] = [m.to_dict() for m in messages]
        response = ConverseResponse.from_dict(self.client.converse(**payload))
        response.model_id = self.model_id
        for callback in self.callbacks:
            callback.on_converse_end(response)
        return response

    def remove_invalid_caching(self, messages):
        if not any(model in self.model_id.lower() for model in self.CACHE_SUPPORTED_MODELS):
            for message in self.messages:
                message.content = [content for content in message.content if not content.cache_point]
            if messages:
                for message in messages:
                    message.content = [content for content in message.content if not content.cache_point]
            self.system = [system for system in self.system if not system.cache_point]
            if self.tool_config:
                self.tool_config.tools = [tool for tool in self.tool_config.tools if not tool.cache_point]

    async def _aget_response(self, messages=None):
        for callback in self.callbacks:
            if hasattr(callback, 'on_converse_start'):
                callback.on_converse_start(self)
        self.remove_invalid_caching(messages)
        loop = asyncio.get_event_loop()
        payload = self.to_dict()
        if messages:
            payload['messages'] = [m.to_dict() for m in messages]
        response_dict = await loop.run_in_executor(None, lambda: self.client.converse(**payload))
        response = ConverseResponse.from_dict(response_dict)
        response.model_id = self.model_id
        for callback in self.callbacks:
            if hasattr(callback, 'on_converse_end'):
                callback.on_converse_end(response)
        return response

    def converse(self, message: Message | str = None):
        if isinstance(message, str):
            message = Message().add_text(message)
        if message:
            self.messages.append(message)
        response = self._get_response()
        self.messages.append(response.output.message)
        return self.format_response(response)

    async def aconverse(self, message: Message | str = None):
        if isinstance(message, str):
            message = Message().add_text(message)
        if message:
            self.messages.append(message)
        response = await self._aget_response()
        self.messages.append(response.output.message)
        return self.format_response(response)

    def bind_tools(self, tools: list | Tools):
        if isinstance(tools, Tools):
            self.add_tool(tools)
            return self
        self.tool_config = ConverseToolConfig()
        for tool in tools:
            self.add_tool(tool)
        return self

    @property
    def current_tool_names(self):
        return [tool.tool_spec.name for tool in self.tool_config.tools]

    def add_tool(self, tool):
        if self.tool_config is None:
            self.tool_config = ConverseToolConfig()

        # Check if it's a Tools class instance
        if hasattr(tool, 'get_tools'):
            # Register all tools from the class
            registered_tools = self.tool_registry.register(tool)
            converse_tools = []
            for registered_tool in registered_tools:
                converse_tool = Tool.from_function(registered_tool)
                if converse_tool.tool_spec.name in self.current_tool_names:
                    logger.info(f'{converse_tool.tool_spec.name} already in tool config skipping.')
                else:
                    self.tool_config.tools.append(converse_tool)
                converse_tools.append(converse_tool)
            return converse_tools

        # Handle single tool
        converse_tool = None
        if callable(tool) and hasattr(tool, '_tool_spec'):
            converse_tool = Tool.from_function(tool)
            self.tool_registry.register(tool)
        elif inspect.isclass(tool) and issubclass(tool, BaseModel):
            converse_tool = Tool.from_pydantic(tool)

        if converse_tool is None:
            raise ValueError(
                'Provided tool is not a tool. Please use a pydantic model, the @tool decorator, or a Tools class instance')
        if converse_tool.tool_spec.name in self.current_tool_names:
            logger.info(f'{converse_tool.tool_spec.name} already in tool config skipping.')
        else:
            self.tool_config.tools.append(converse_tool)
        return converse_tool

    def add_system(self, system):
        self.system.append(SystemContent(text=system))

    def add_system_cache_point(self):
        self.system.append(SystemContent(cache_point=CachePoint()))

    def set_tool_choice(self, tool_name):
        if inspect.isclass(tool_name) and issubclass(tool_name, BaseModel):
            tool_name = tool_name.__name__
        self.tool_config.tool_choice = ToolChoice(tool=ToolChoiceTool(name=tool_name))

    def with_structured_output(self, output_model, force_choice=True, skip_add_tool=False, first_tool_only=True):
        assert not (skip_add_tool is True and len(
            self.tool_config.tools) == 0), "If you skip_add_tool you must add tools manually using bind_tools."
        # noinspection PyArgumentList
        return structured_model_factory(self.model_id)(
            model_id=self.model_id,
            messages=self.messages.copy(),
            system=self.system,
            inference_config=self.inference_config,
            tool_config=self.tool_config,
            guardrail_config=self.guardrail_config,
            additional_model_request_fields=self.additional_model_request_fields,
            prompt_variables=self.prompt_variables,
            additional_model_response_field_paths=self.additional_model_response_field_paths,
            request_metadata=self.request_metadata,
            performance_config=self.performance_config,
            region_name=self.region_name,
            callbacks=self.callbacks,
            _client=self.client,
            _async_client=self._async_client,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            output_model=output_model,
            force_choice=force_choice,
            skip_add_tool=skip_add_tool,
            first_tool_only=first_tool_only
        )


@dataclass
class StructuredConverse(Converse):
    output_model: BaseModel = None
    force_choice: bool = True
    skip_add_tool: bool = False
    first_tool_only: bool = True

    def __post_init__(self):
        super()._TO_DICT_EXCLUSIONS.extend(['output_model', 'force_choice', 'skip_add_tool', 'first_tool_only'])
        if self.output_model is None:
            raise ValueError(f'Need to specify output_model for StructuredConverse')
        if not self.skip_add_tool:
            self.add_tool(self.output_model)
        if self.force_choice and 'claude' in self.model_id:
            self.set_tool_choice(self.output_model.__name__)

    def invoke(self, message: Message | str, retries=1):
        response = self._get_response(self._format_invoke_message(message))
        try:
            return self.format_response(response)
        except ValidationError as e:
            if retries <= 0:
                raise
            message.add_text(
                f'Your last response failed validation. You have {retries} retires left. Please correct the following errors and try again:\n{e}')
            return self.invoke(message, retries=retries - 1)

    async def ainvoke(self, message: Message | str, retries=1):
        response = await self._aget_response(self._format_invoke_message(message))
        try:
            return self.format_response(response)
        except ValidationError as e:
            if retries <= 0:
                raise
            message.add_text(
                f'Your last response failed validation. You have {retries} retires left. Please correct the following errors and try again:\n{e}')
            return await self.ainvoke(message, retries=retries - 1)

    def format_response(self, response):
        response_objects = []
        response_texts = []
        for content in response.output.message.content:
            if content.tool_use:
                response_objects.append(self.output_model.model_validate(content.tool_use.input))
            if content.text:
                response_texts.append(content.text)
        if not response_objects:
            response_text = '\n'.join(response_texts)
            logging.error(f"Failed to call structured output. Response text: \n{response_text}")
            return None
        # Return first only
        if self.first_tool_only:
            return response_objects[0]
        return response_objects


@dataclass
class StructuredMaverick(StructuredConverse):
    def __post_init__(self):
        super()._TO_DICT_EXCLUSIONS.extend(['output_model', 'force_choice'])
        if self.output_model is None:
            raise ValueError(f'Need to specify output_model for StructuredConverse')
        schema = self.output_model.model_json_schema()
        prompt_addition = f"""

You must respond with valid JSON that matches this schema:
{json.dumps(schema, indent=2)}

CRITICAL RULES:
- Output ONLY valid JSON starting with {{ and ending with }}
- Use double quotes for all strings
- Include all required fields
- Use null for missing optional values
- No comments, no markdown, no explanations"""
        if self.system:
            self.system[0] = SystemContent(text=self.system[0].text + prompt_addition)
        else:
            self.add_system(prompt_addition)

    def format_response(self, response):
        response_text = ''.join(content.text for content in response.output.message.content if content.text)
        json_match = re.search(r'(\{(?:[^{}]|(?:\{[^{}]*\}))*\})', response_text, re.DOTALL)
        if not json_match:
            logging.error(f"No JSON found in response: {response_text}")
            return None
        json_str = json_match.group(1)
        try:
            parsed_data = json.loads(json_str)
            return self.output_model.model_validate(parsed_data)
        except json.JSONDecodeError as e:
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            json_str = re.sub(r':\s*(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?)', lambda m: ': ' + m.group(1).replace(',', ''),
                              json_str)
            try:
                parsed_data = json5.loads(json_repair.repair_json(json_str))
                return self.output_model.model_validate(parsed_data)
            except Exception:
                logging.error(f"Failed to parse JSON: {e}\nResponse: {response_text}")
                return None


CUSTOM_STRUCTURED_MODELS = {
    'llama4-maverick': StructuredMaverick
}


def structured_model_factory(model_id):
    for model, structured_class in CUSTOM_STRUCTURED_MODELS.items():
        if model in model_id.lower():
            return structured_class
    return StructuredConverse


class Finish(BaseModel):
    """ Return this object when you have completed you task """
    final_response: str


@dataclass
class ConverseAgent(Converse):
    max_iterations: int = 15
    exit_tool: Optional[Tool] = None
    structured_output: Optional[BaseModel] = None
    debug: bool = False

    def __post_init__(self):
        super()._TO_DICT_EXCLUSIONS.extend(['max_iterations', 'exit_tool', 'structured_output', 'debug'])

    def bind_exit_tool(self, tool):
        self.exit_tool = self.add_tool(tool)

    def with_structured_output(self, base_model, **kwargs):
        self.bind_exit_tool(base_model)
        self.structured_output = base_model

    def unbind_structured_output(self):
        self.exit_tool = None
        self.structured_output = None

    def run(self, message: Message | str = None, max_iterations=None, first_tool_only=True):
        max_iterations = max_iterations or self.max_iterations

        if self.structured_output:
            self.bind_exit_tool(self.structured_output)
        elif self.exit_tool is None:
            self.bind_exit_tool(Finish)

        if isinstance(message, str):
            message = Message().add_text(message)
        if message:
            self.messages.append(message)
        for iteration in range(max_iterations):
            response = self._get_response()
            if not response.output.message.content:
                last_content_text = self.messages[-1].content[-1].text
                logger.error(last_content_text)
                return last_content_text
            self.messages.append(response.output.message)
            tool_results = []
            exit_tool_results = []
            for content in response.output.message.content:
                if content.tool_use:
                    tool_name = content.tool_use.name
                    tool_input = content.tool_use.input
                    tool_use_id = content.tool_use.tool_use_id
                    if self.debug:
                        logger.warning(f'Called {tool_name} for {tool_input}')
                    try:

                        if tool_name == self.exit_tool.tool_spec.name:
                            if self.structured_output:
                                result = self.structured_output.model_validate(tool_input)
                            else:
                                result = Finish.model_validate(tool_input).final_response
                            exit_tool_results.append(result)
                        else:
                            result = self.tool_registry.execute(tool_name, tool_input)
                        tool_result = ToolResult(
                            tool_use_id=tool_use_id,
                            content=[ToolResultContent(text=str(result))],
                            status="success"
                        )
                    except Exception as e:
                        tool_result = ToolResult(
                            tool_use_id=tool_use_id,
                            content=[ToolResultContent(text=f"Tool Call FAILED! Exception {e}. Trace: {traceback.print_exc()}")],
                            status="error"
                        )
                        if self.debug:
                            logger.warning(f'FAILED {tool_name}: {e}')
                    tool_results.append(tool_result)
            if tool_results:
                tool_message = Message(role="user")
                for result in tool_results:
                    tool_message.content.append(MessageContent(tool_result=result))
                self.messages.append(tool_message)
            if exit_tool_results:
                if first_tool_only:
                    return exit_tool_results[0]
                return exit_tool_results
        return f"Agent reached maximum iterations ({max_iterations}) without calling exit tool"
