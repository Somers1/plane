import datetime
import logging
from importlib import import_module
from typing import Type, Dict, Any, Optional, List
from uuid import UUID

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from pydantic import BaseModel, Field, create_model, field_validator

logger = logging.getLogger(__name__)


class Lazy:
    def __init__(self, cls):
        self._cls = cls
        self._instance = None

    def __getattr__(self, name):
        if self._instance is None:
            self._instance = self._cls()
        return getattr(self._instance, name)

    def __call__(self, *args, **kwargs):
        if self._instance is None:
            self._instance = self._cls(*args, **kwargs)
        return self._instance


class LazyImport:
    def __init__(self, module_name):
        self.module_name = module_name
        self.module = None

    def __getattr__(self, name):
        if self.module is None:
            print(f'Importing module {self.module_name}')
            self.module = import_module(self.module_name)
        return getattr(self.module, name)

    def __call__(self, *args, **kwargs):
        if self.module is None:
            print(f'Importing module {self.module_name}')
            self.module = import_module(self.module_name)
        return self.module(*args, **kwargs)


def check_pdf_encoding_issues(text):
    has_null_bytes = '\x00' in text
    has_unexpected_bytes = any(ord(c) < 32 and c not in '\n\r\t' for c in text)
    return has_null_bytes or has_unexpected_bytes


def get_image_assisted_prompt(prompt, image):
    content = {"role": "user", "content": [{"type": "text", "text": prompt}]}
    if image:
        content['content'].append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}"}})
    return [content]


DJANGO_TYPE_MAP = {
    models.CharField: str,
    models.TextField: str,
    ArrayField: list,
    models.IntegerField: int,
    models.FloatField: float,
    models.BooleanField: bool,
    models.DateField: str,
    models.DateTimeField: str,
    models.ForeignKey: int,
    models.ManyToManyField: list,
}

def get_agent_field_type():
    from agent.fields import AgentField
    return AgentField

def get_validate_field(field):
    def validate_field(v):
        if isinstance(v, str):
            if 'unknown' in v.lower():
                return None
            if 'N/A' in v.upper():
                return None
            if not v:
                return None
        return v
    return validate_field


def django_to_pydantic(django_model: Type[models.Model]) -> Type[BaseModel]:
    from agent.fields import AgentField
    fields = {}
    validators = {}
    for field in django_model._meta.get_fields():
        if not getattr(field, 'help_text', None):
            continue
        if isinstance(field, AgentField):
            value_help = field.value_help or field.help_text
            AgentFieldValueModel = create_model(
                f'{field.name}_AgentFieldValue',
                value=(Optional[str], Field(default=None, description=value_help)),
                explanation=(Optional[str], Field(default=None, description=field.explanation_help))
            )
            field_type = AgentFieldValueModel
        elif field.is_relation:
            if field.many_to_many:
                field_type = list
            else:
                field_type = DJANGO_TYPE_MAP.get(type(field.target_field), str)
        else:
            field_type = DJANGO_TYPE_MAP.get(type(field), str)

        field_type = Optional[field_type]
        default = None
        if field.has_default():
            default = field.default
        if not isinstance(field, AgentField):
            validators[f'{field.name}_validator'] = field_validator(field.name, mode='before')(get_validate_field(field))
        fields[field.name] = (field_type, Field(default=default, description=field.help_text))

    class DjangoPydantic(BaseModel):
        def to_django(self) -> models.Model:
            from agent.fields import AgentFieldValue
            data = self.model_dump()
            for field in django_model._meta.get_fields():
                if isinstance(field, AgentField) and field.name in data and data[field.name]:
                    if isinstance(data[field.name], dict):
                        data[field.name] = AgentFieldValue(data[field.name])
            return django_model(**data)

    pydantic_model = create_model(f"{django_model.__name__}Pydantic", **fields, __base__=DjangoPydantic,
                                  __validators__=validators)
    return pydantic_model
