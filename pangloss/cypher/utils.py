import typing
import uuid

import pydantic

from pangloss.model_config.models_base import RootNode, ReifiedRelation


class Identifier(str):
    def __new__(cls):
        return super().__new__(cls, "x" + uuid.uuid4().hex[:6].lower())


class QuerySubstring(str):
    def __new__(cls, query_string: str):
        return super().__new__(cls, query_string)


class QueryParams(dict[Identifier, dict[str, typing.Any]]):
    pass


class CreateQuery:
    match_query_strings: list[str]
    create_query_strings: list[str]
    query_params: dict[str, typing.Any]
    return_identifier: str
    return_uuid: uuid.UUID

    def __init__(self):
        self.match_query_strings = []
        self.create_query_strings = []
        self.query_params = {}
        self.uuid = uuid.uuid4()

    def to_query_string(self):
        if not self.return_identifier:
            raise Exception("CreateQuery.to_query_string called on non-top-level node")
        return f"""{"\n".join(self.match_query_strings)}
    {"\n".join(self.create_query_strings)}
    RETURN {self.return_identifier}"""


def join_labels(labels: set[str], extra_labels: typing.Iterable[str]):
    all_labels = [*labels, *extra_labels]
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


def convert_dict_for_writing(data: dict[str, typing.Any]):
    return {key: convert_type_for_writing(value) for key, value in data.items()}


def get_properties_as_writeable_dict(
    instance: RootNode | ReifiedRelation, extras: dict[str, typing.Any] | None = None
):
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
            if value := getattr(instance, property_definition.field_name, None):
                data[property_definition.field_name] = convert_type_for_writing(value)
    if extras:
        for key, value in extras.items():
            data[key] = convert_type_for_writing(value)

    return data
