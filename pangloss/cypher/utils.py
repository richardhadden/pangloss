import uuid

import pydantic

from pangloss.model_config.models_base import RootNode, ReifiedRelation


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


def get_properties_as_writeable_dict(cls: RootNode | ReifiedRelation):
    data = {}
    for property_definition in cls.field_definitions.property_fields:
        if property_definition.field_metatype == "MultiKeyField":
            for key, value in dict(
                getattr(cls, property_definition.field_name)
            ).items():
                data[f"{property_definition.field_name}____{key}"] = (
                    convert_type_for_writing(value)
                )

        else:
            data[property_definition.field_name] = convert_type_for_writing(
                getattr(cls, property_definition.field_name)
            )

    return data
