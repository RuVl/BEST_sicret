from functools import lru_cache
from typing import TYPE_CHECKING

# Import other classes locally to avoid circular import error
if TYPE_CHECKING:
    from includes.templates.contexts import BaseContext
    from includes.templates.contexts import Formatter
    from includes.templates.contexts import Validator
    # смысла переписывать нет, если мне надо +- такое же использовать


@lru_cache
def get_formatter(type_name: str) -> 'Formatter':
    from includes.templates.formatters import StringFormatter, IntegerFormatter, NumberFormatter, BooleanFormatter, DummyFormatter
    mapping = {
        'string': StringFormatter(),
        'integer': IntegerFormatter(),
        'number': NumberFormatter(),
        'boolean': BooleanFormatter(),
    }
    return mapping.get(type_name, DummyFormatter(type_name))  # fallback


@lru_cache
def get_validator(format_name: str) -> 'Validator':
    from includes.templates.validators import DateValidator, DummyValidator
    mapping = {
        'date': DateValidator(),
    }
    return mapping.get(format_name, DummyValidator(format_name))


def create_context(schema: dict, parent: 'BaseContext' = None, required: bool = False) -> 'BaseContext':
    from includes.templates.contexts import ObjectContext, ArrayContext, PrimitiveContext
    type_mapping = {
        'object': ObjectContext,
        'array': ArrayContext,
        'string': PrimitiveContext,
        'integer': PrimitiveContext,
        'number': PrimitiveContext,
        'boolean': PrimitiveContext,
    }

    context_class = type_mapping.get(schema.get('type'))
    if context_class:
        return context_class(schema, parent, required=required)

    raise ValueError(f"Unknown type: {schema.get('type')}")
