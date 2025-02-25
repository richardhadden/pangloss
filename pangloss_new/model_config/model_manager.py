import typing

from pangloss_new.exceptions import PanglossInitialisationError

if typing.TYPE_CHECKING:
    from pangloss_new.model_config.models_base import (
        EdgeModel,
        MultiKeyField,
        ReifiedRelation,
        RootNode,
    )


class ModelManager:
    base_models: dict[str, type["RootNode"]] = {}
    reified_relation_models: dict[str, type["ReifiedRelation"]] = {}
    edge_models: dict[str, type["EdgeModel"]] = {}
    multikeyfields_models: dict[str, type["MultiKeyField"]] = {}

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
    def register_reified_relation_model(
        cls, reified_relation_model: type["ReifiedRelation"]
    ):
        # Supposedly, this checks whether the model is a "root" generic class
        # e.g. Intermediate[T]
        # or the "instantiation" of a generic class, e.g. Intermediate[Cat]
        # If the former, add it to model manager
        if reified_relation_model.__pydantic_generic_metadata__["origin"]:
            cls.reified_relation_models[reified_relation_model.__name__] = (
                reified_relation_model
            )

    @classmethod
    def register_multikeyfield_model(cls, multikeyfield_model: type["MultiKeyField"]):
        if multikeyfield_model.__pydantic_generic_metadata__["origin"]:
            cls.multikeyfields_models[multikeyfield_model.__name__] = (
                multikeyfield_model
            )

    @classmethod
    def register_edge_model(cls, edge_model: type["EdgeModel"]):
        cls.edge_models[edge_model.__name__] = edge_model

    @classmethod
    def initialise_models(cls, _defined_in_test: bool = False):
        from pangloss_new.model_config.model_setup_functions.build_create_model import (
            build_create_model,
        )
        from pangloss_new.model_config.model_setup_functions.build_model_meta import (
            initialise_model_meta_inheritance,
        )
        from pangloss_new.model_config.model_setup_functions.build_pg_annotations import (
            build_pg_annotations,
        )
        from pangloss_new.model_config.model_setup_functions.build_pg_model_definition import (
            build_pg_model_definitions,
        )
        from pangloss_new.model_config.model_setup_functions.build_reference_model import (
            build_reference_create,
            build_reference_set,
            build_reference_view,
        )
        from pangloss_new.model_config.model_setup_functions.set_type_on_base_model import (
            set_type_to_literal_on_base_model,
        )

        for model_name, model in cls.multikeyfields_models.items():
            build_pg_annotations(model)
            build_pg_model_definitions(model)

        for model_name, model in cls.base_models.items():
            set_type_to_literal_on_base_model(model)
            build_pg_annotations(model)

        for model_name, model in cls.reified_relation_models.items():
            set_type_to_literal_on_base_model(model)

        for model_name, model in cls.base_models.items():
            build_pg_model_definitions(model)

        for model_name, model in cls.base_models.items():
            initialise_model_meta_inheritance(model)

        for model_name, model in cls.reified_relation_models.items():
            build_pg_annotations(model)

        for model_name, model in cls.reified_relation_models.items():
            build_pg_model_definitions(model)

        for model_name, model in cls.edge_models.items():
            build_pg_annotations(model)

        for model_name, model in cls.edge_models.items():
            build_pg_model_definitions(model)

        for model_name, model in cls.base_models.items():
            build_reference_set(model)
            build_reference_view(model)
            build_reference_create(model)

        for model_name, model in cls.base_models.items():
            build_create_model(model)
