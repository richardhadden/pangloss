import typing

from pydantic import create_model

from pangloss_new.model_config.models_base import (
    ReferenceSetBase,
    ReferenceViewBase,
    RootNode,
)


def build_reference_set(model: type["RootNode"]):
    # Reference Setter only needs an identifier and a type
    model.ReferenceSet = create_model(
        f"{model.__name__}ReferenceSet",
        __base__=ReferenceSetBase,
        __module__=model.__module__,
        type=(typing.Literal[model.__name__], model.__name__),
    )
    model.ReferenceSet.__pg_base_class__ = model


def build_reference_view(model: type["RootNode"]):
    extra_fields = {}

    model.ReferenceView = create_model(
        f"{model.__name__}ReferenceView",
        __base__=ReferenceViewBase,
        __module__=model.__module__,
        type=(typing.Literal[model.__name__], model.__name__),
    )
    model.ReferenceView.__pg_base_class__ = model
