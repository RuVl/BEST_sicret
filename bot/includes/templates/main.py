from functools import lru_cache
from typing import TYPE_CHECKING

# Import other classes locally to avoid circular import error
if TYPE_CHECKING:
	from .contexts import BaseContext
	from .formatters import Formatter
	from .validators import Validator


@lru_cache
def get_formatter(type_name: str) -> 'Formatter':
	from .formatters import StringFormatter, IntegerFormatter, NumberFormatter, BooleanFormatter, DummyFormatter
	mapping = {
		'string': StringFormatter(),
		'integer': IntegerFormatter(),
		'number': NumberFormatter(),
		'boolean': BooleanFormatter(),
	}
	return mapping.get(type_name, DummyFormatter())  # fallback


@lru_cache
def get_validator(format_name: str) -> 'Validator':
	from .validators import DateValidator, DummyValidator
	mapping = {
		'date': DateValidator(),
	}
	return mapping.get(format_name, DummyValidator())


def create_context(schema: dict, parent: 'BaseContext' = None, required: bool = False) -> 'BaseContext':
	from includes.templates.contexts import ObjectContext, ArrayContext, PrimitiveContext
	type_mapping = {
		'object': ObjectContext,
		'array': ArrayContext,
		'string': PrimitiveContext,
		'integer': PrimitiveContext,
		'number': PrimitiveContext,
		'boolean': PrimitiveContext,
		# Add other types as needed
	}

	context_class = type_mapping.get(schema.get('type'))
	if context_class:
		return context_class(schema, parent, required=required)

	raise ValueError(f"Unknown type: {schema.get('type')}")
