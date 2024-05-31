import typing


if typing.TYPE_CHECKING:
    from pangloss.model_config.models_base import RootNode


class ModelManager:
    registered_models: list[type["RootNode"]] = []

    @classmethod
    def register_model(cls, model: type["RootNode"]):
        cls.registered_models.append(model)

    @classmethod
    def _reset(cls):
        cls.registered_models = []

    @classmethod
    def initialise_models(cls, _defined_in_test=False):
        from pangloss.model_config.model_setup_functions import (
            initialise_model_field_definitions,
            delete_indirect_non_heritable_trait_fields,
            initialise_reference_set_on_base_models,
            initialise_reference_view_on_base_models,
            initialise_outgoing_relation_types_on_base_model,
        )

        for model in cls.registered_models:
            model.model_rebuild(_parent_namespace_depth=3 if _defined_in_test else 2)

            delete_indirect_non_heritable_trait_fields(model)

            model.model_rebuild(_parent_namespace_depth=3 if _defined_in_test else 2)
            initialise_model_field_definitions(model)

            initialise_reference_set_on_base_models(model)
            initialise_reference_view_on_base_models(model)

        for model in cls.registered_models:
            initialise_outgoing_relation_types_on_base_model(model)
            model.model_rebuild(_parent_namespace_depth=3 if _defined_in_test else 2)
