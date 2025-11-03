import logging
import os
from functools import cached_property

from django.db import models
from django.utils import timezone

from .bedrock_sdk.converse import Converse, ConverseInferenceConfig, BaseCallbackHandler, ConverseResponse, TokenUsage, \
    ConverseAgent
from . import utils
from .bedrock_sdk.embedding import BedrockEmbedding

logger = logging.getLogger(__name__)

import time


class LLMManager(models.Manager):
    @cached_property
    def strong(self):
        return self.get(production_model=self.model.STRONG)

    @cached_property
    def hybrid(self):
        return self.get(production_model=self.model.HYBRID)

    @cached_property
    def thinking(self):
        return self.get(production_model=self.model.THINKING)

    @cached_property
    def weak(self):
        return self.get(production_model=self.model.WEAK)

    @cached_property
    def tiny(self):
        return self.get(production_model=self.model.TINY)

    @cached_property
    def embed(self):
        return self.get(production_model=self.model.EMBED)

    @cached_property
    def agent(self):
        return self.get(production_model=self.model.AGENT)

def get_wrapper(base_class):
    class ChatWrapper(base_class):
        def with_structured_output(self, model_class):
            if issubclass(model_class, models.Model):
                model_class = utils.django_to_pydantic(model_class)
            return super().with_structured_output(model_class)
    return ChatWrapper


class Model(models.Model):
    BEDROCK = 'bedrock'
    BEDROCK_EMBED = 'bedrock_embed'
    providers = [
        (BEDROCK, BEDROCK.title()),
    ]

    STRONG = 'strong'
    WEAK = 'weak'
    TINY = 'tiny'
    EMBED = 'embed'
    THINKING = 'thinking'
    HYBRID = 'hybrid'
    AGENT = 'agent'

    production_models = [
        (STRONG, STRONG.title()),
        (WEAK, WEAK.title()),
        (TINY, TINY.title()),
        (EMBED, EMBED.title()),
        (THINKING, THINKING.title()),
        (HYBRID, HYBRID.title()),
        (AGENT, AGENT.title()),
    ]

    model_id = models.CharField(max_length=255)
    max_tokens = models.IntegerField(null=True)
    temperature = models.FloatField(null=True)
    additional_model_request_fields = models.JSONField(null=True)
    region_name = models.CharField(max_length=255, null=True)
    prompt_cost = models.FloatField(null=True)
    completion_cost = models.FloatField(null=True)
    cached_write_cost = models.FloatField(null=True)
    cached_read_cost = models.FloatField(null=True)
    provider = models.CharField(max_length=255, null=True, choices=providers)
    production_model = models.CharField(max_length=255, null=True, choices=production_models, unique=True)

    objects = models.Manager()
    llms = LLMManager()

    @property
    def _llm(self):
        if self.provider == self.BEDROCK:
            return get_wrapper(Converse)(
                model_id=self.model_id,
                inference_config=ConverseInferenceConfig(max_tokens=self.max_tokens, temperature=self.temperature),
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=self.region_name,
                callbacks=[DjangoMetricsCallback(self)]
            )
        if self.provider == self.BEDROCK_EMBED:
            return BedrockEmbedding(
                model_id=self.model_id,
                region_name=self.region_name,
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
        raise ValueError(f'Unknown provider {self.provider}')

    def __getattr__(self, item):
        return getattr(self._llm, item)

    def as_agent(self, max_iterations=15, exit_tool=None, structured_output=None, debug=False):
        return get_wrapper(ConverseAgent)(
            model_id=self.model_id,
            inference_config=ConverseInferenceConfig(max_tokens=self.max_tokens, temperature=self.temperature),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=self.region_name,
            callbacks=[DjangoMetricsCallback(self)],
            max_iterations=max_iterations,
            exit_tool=exit_tool,
            structured_output=structured_output,
            debug=debug
        )

    def usage_callback(self, timestamp, usage: TokenUsage):
        cost = InvokeCost(timestamp=timestamp, model_id=self.model_id)
        cost.duration = time.time() - timestamp.timestamp()
        cost.completion_tokens = usage.output_tokens
        cost.prompt_tokens = usage.input_tokens
        cost.cached_write_tokens = usage.cache_write_input_tokens or 0
        cost.cached_read_tokens = usage.cache_read_input_tokens or 0
        cost.prompt_cost = (cost.prompt_tokens / 1000) * (self.prompt_cost or 0)
        cost.completion_cost = (cost.completion_tokens / 1000) * (self.completion_cost or 0)
        cost.cached_write_cost = (cost.cached_write_tokens / 1000) * (self.cached_write_cost or 0)
        cost.cached_read_cost = (cost.cached_read_tokens / 1000) * (self.cached_read_cost or 0)
        cost.save()


class DjangoMetricsCallback(BaseCallbackHandler):
    def __init__(self, model):
        self.start_time = None
        self.model = model

    def on_converse_start(self, converse) -> None:
        self.start_time = timezone.now()

    def on_converse_end(self, response: ConverseResponse):
        return self.model.usage_callback(self.start_time, response.usage)


class InvokeCost(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    duration = models.FloatField(null=True)
    model = models.ForeignKey(Model, on_delete=models.CASCADE)
    completion_tokens = models.IntegerField(null=True)
    prompt_tokens = models.IntegerField(null=True)
    cached_write_tokens = models.IntegerField(null=True)
    cached_read_tokens = models.IntegerField(null=True)
    prompt_cost = models.FloatField(null=True)
    completion_cost = models.FloatField(null=True)
    cached_write_cost = models.FloatField(null=True)
    cached_read_cost = models.FloatField(null=True)


class Prompt(models.Model):
    name = models.CharField(max_length=255)
    prompt = models.TextField(null=True)

    @classmethod
    def get(cls, name):
        try:
            return cls.objects.get(name=name).prompt
        except Prompt.DoesNotExist:
            return None


llm = Model.llms
