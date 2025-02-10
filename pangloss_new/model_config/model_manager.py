import typing

from pangloss_new.exceptions import PanglossInitialisationError

if typing.TYPE_CHECKING:
    from pangloss_new.model_config.models_base import ReifiedRelation, RootNode


class ModelManager:
    base_models: dict[str, type["RootNode"]] = {}
    reified_relation_models: dict[str, type["ReifiedRelation"]] = {}

    def __init__(self):
        raise PanglossInitialisationError("ModelManager class cannot be initialised")

    @classmethod
    def _reset(cls):
        cls.base_models = {}
        cls.reified_relation_models = {}

    @classmethod
    def register_base_model(cls, base_model: type["RootNode"]):
        if base_model.__name__ == "BaseNode":
            return

        cls.base_models[base_model.__name__] = base_model

    @classmethod
    def register_reified_relation_model(cls, reified_relation_model):
        cls.reified_relation_models[reified_relation_model.__name__] = (
            reified_relation_model
        )

    @classmethod
    def initialise_models(cls, _defined_in_test: bool = False):
        from pangloss_new.model_config.model_setup_functions.build_pg_annotations import (
            build_pg_annotations,
        )
        from pangloss_new.model_config.model_setup_functions.build_pg_model_definition import (
            build_pg_model_definitions,
        )
        from pangloss_new.model_config.model_setup_functions.set_type_on_base_model import (
            set_type_to_literal_on_base_model,
        )

        for model_name, model in cls.base_models.items():
            set_type_to_literal_on_base_model(model)
            build_pg_annotations(model)

        for model_name, model in cls.reified_relation_models.items():
            set_type_to_literal_on_base_model(model)

        for model_name, model in cls.base_models.items():
            build_pg_model_definitions(model)
