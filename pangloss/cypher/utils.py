import typing
import uuid

import pydantic

from pangloss.model_config.models_base import RootNode, ReifiedRelation


class QuerySubstring(str):
    def __new__(cls, query):
        return super().__new__(cls, query)


class Identifier(str):
    def __new__(cls):
        return super().__new__(cls, "x" + uuid.uuid4().hex[:6].lower())


class QueryParams(dict[Identifier, dict[str, typing.Any]]):
    pass


def join_labels(labels: set[str], extra_labels: typing.Iterable[str]):
    all_labels = list(*labels, *extra_labels)
    return f"{":".join(all_labels)}"


def convert_type_for_writing(value):
    match value:
        case uuid.UUID():
            return str(value)
        case pydantic.AnyUrl():
            return str(value)
        case set():
            return list(value)
        case tuple():
            return list(value)
        case _:
            return value


def get_properties_as_writeable_dict(instance: RootNode | ReifiedRelation):
    data = {}
    for property_definition in instance.field_definitions.property_fields:
        if property_definition.field_metatype == "MultiKeyField":
            for key, value in dict(
                getattr(instance, property_definition.field_name)
            ).items():
                data[f"{property_definition.field_name}____{key}"] = (
                    convert_type_for_writing(value)
                )

        else:
            data[property_definition.field_name] = convert_type_for_writing(
                getattr(instance, property_definition.field_name)
            )

    return data
