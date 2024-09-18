import collections
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
            set_type_to_literal_on_base_model,
            initialise_model_field_definitions,
            build_incoming_relation_definitions,
            delete_indirect_non_heritable_trait_fields,
            initialise_reference_set_on_base_models,
            initialise_reference_view_on_base_models,
            initialise_outgoing_relation_types_on_base_model,
            initialise_embedded_nodes_on_base_model,
            initialise_view_type_for_base,
            initialise_incoming_relations_on_view_types_for_base,
        )

        for model in cls.registered_models:
            model.model_rebuild(_parent_namespace_depth=3 if _defined_in_test else 2)
            set_type_to_literal_on_base_model(model)
            delete_indirect_non_heritable_trait_fields(model)

            model.model_rebuild(_parent_namespace_depth=3 if _defined_in_test else 2)
            initialise_model_field_definitions(model)

            initialise_reference_set_on_base_models(model)
            initialise_reference_view_on_base_models(model)
            model.incoming_relation_definitions = collections.defaultdict(set)

        for model in cls.registered_models:
            initialise_outgoing_relation_types_on_base_model(model)
            model.model_rebuild(
                force=True, _parent_namespace_depth=3 if _defined_in_test else 2
            )
            initialise_embedded_nodes_on_base_model(model)
            model.model_rebuild(
                force=True, _parent_namespace_depth=3 if _defined_in_test else 2
            )

        for model in cls.registered_models:
            initialise_view_type_for_base(model)
            model.model_rebuild(
                force=True, _parent_namespace_depth=3 if _defined_in_test else 2
            )

        # New strategy... initialise View type first, then build incoming relations and
        # initialise incoming relations on View type
        for model in cls.registered_models:
            build_incoming_relation_definitions(model)

        for model in cls.registered_models:
            initialise_incoming_relations_on_view_types_for_base(model)
