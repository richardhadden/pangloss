import dataclasses
import typing

import annotated_types


@dataclasses.dataclass
class RelationConfig:
    reverse_name: str
    subclasses_relation: typing.Optional[list[str] | frozenset[str]] = None
    edge_model: typing.Optional[type["EdgeModel"]] = None
    validators: typing.Sequence[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )

    create_inline: bool = False
    edit_inline: bool = False
    delete_related_on_detach: bool = False
    default_type: typing.Optional[str] = None

    def __hash__(self):
        if self.subclasses_relation:
            self.subclasses_relation = frozenset(self.subclasses_relation)
        return hash(self.__dict__)
