import dataclasses

from pangloss_new.model_config.field_definitions import (
    EmbeddedFieldDefinition,
    RelationFieldDefinition,
    RelationToNodeDefinition,
    RelationToReifiedDefinition,
)
from pangloss_new.model_config.model_setup_functions.utils import (
    get_concrete_model_types,
)
from pangloss_new.model_config.models_base import ReifiedRelation, RootNode


@dataclasses.dataclass
class PathSegment:
    type: type[RootNode] | type[ReifiedRelation]
    relation_definition: RelationFieldDefinition | EmbeddedFieldDefinition | None = None

    def __repr__(self):
        if self.relation_definition:
            return f"""PathSegment(type={self.type.__name__}, relation_name="{self.relation_definition.field_name}")"""
        else:
            return f"PathSegment(type={self.type.__name__})"

    def __hash__(self) -> int:
        return hash(self.type.__name__ + str(hash(self.relation_definition)))


class Path(list[PathSegment]):
    def __init__(self, *args):
        super().__init__(args)

    def __hash__(self) -> int:
        return hash("|".join(str(self)))


def get_reverse_relation_paths(
    model: type[RootNode] | type[ReifiedRelation],
    path_components: list[PathSegment] | None = None,
    paths: list[Path] | None = None,
) -> list[Path]:
    if not path_components:
        path_components = []
    if not paths:
        paths = []

    for relation_defintion in model._meta.fields.relation_fields:
        for field_type_definition in relation_defintion.field_type_definitions:
            if isinstance(field_type_definition, RelationToNodeDefinition):
                paths.append(
                    Path(
                        *path_components,
                        PathSegment(
                            relation_definition=relation_defintion,
                            type=model,
                        ),
                        PathSegment(type=field_type_definition.annotated_type),
                    )
                )
            if isinstance(field_type_definition, RelationToReifiedDefinition):
                get_reverse_relation_paths(
                    field_type_definition.annotated_type,
                    path_components=[
                        *path_components,
                        PathSegment(type=model, relation_definition=relation_defintion),
                    ],
                    paths=paths,
                )
    for embedded_definition in model._meta.fields.embedded_fields:
        for field_concrete_type in get_concrete_model_types(
            embedded_definition.field_annotation, include_subclasses=True
        ):
            get_reverse_relation_paths(
                model=field_concrete_type,
                path_components=[
                    *path_components,
                    PathSegment(type=model, relation_definition=embedded_definition),
                ],
                paths=paths,
            )

    return paths


def build_reverse_relations_definitions_to(model: type[RootNode]):
    paths = get_reverse_relation_paths(model)
