from typing import Annotated, no_type_check

from pangloss_new import initialise_models
from pangloss_new.model_config.model_setup_functions.build_reverse_relation_definitions import (
    PathSegment,
    get_reverse_relation_paths,
)
from pangloss_new.model_config.models_base import (
    Embedded,
    ReifiedRelation,
    RelationConfig,
)
from pangloss_new.models import BaseNode


@no_type_check
def test_build_reverse_relation_paths():
    class Person(BaseNode):
        pass

    class Dog(BaseNode):
        pass

    class Cat(BaseNode):
        pass

    class Intermediate[T](ReifiedRelation[T]):
        pass

    class WithProxy[T, U](ReifiedRelation[T]):
        proxy: Annotated[U, RelationConfig(reverse_name="acts_as_proxy_in")]

    class Reference(BaseNode):
        pass

    class Citation(BaseNode):
        cites: Annotated[Reference, RelationConfig(reverse_name="is_cited_in")]
        cites_via_intermediate: Annotated[
            Intermediate[Reference], RelationConfig(reverse_name="is_cited_in")
        ]

    class Event(BaseNode):
        involves_entity: Annotated[
            Person
            | Dog
            | Intermediate[Cat]
            | WithProxy[Intermediate[Cat], Intermediate[Dog]],
            RelationConfig(reverse_name="is_involved_in_event"),
        ]
        involves_dog: Annotated[
            Dog, RelationConfig(reverse_name="is_involved_in_event")
        ]
        source: Embedded[Citation]

    initialise_models()

    # Sanity check: reverse_relations fields initialising correctly
    assert isinstance(Event._meta.fields.reverse_relations, dict)

    paths = get_reverse_relation_paths(Event)

    assert len(paths) == 8

    assert paths[0] == [
        PathSegment(
            type=Event,
            relation_definition=Event._meta.fields["involves_entity"],
        ),
        PathSegment(type=Person),
    ]

    assert paths[1] == [
        PathSegment(
            type=Event,
            relation_definition=Event._meta.fields["involves_entity"],
        ),
        PathSegment(type=Dog),
    ]

    assert paths[2] == [
        PathSegment(
            type=Event,
            relation_definition=Event._meta.fields["involves_entity"],
        ),
        PathSegment(
            type=Intermediate[Cat],
            relation_definition=Intermediate[Cat]._meta.fields["target"],
        ),
        PathSegment(type=Cat),
    ]

    assert paths[3] == [
        PathSegment(
            type=Event,
            relation_definition=Event._meta.fields["involves_entity"],
        ),
        PathSegment(
            type=WithProxy[Intermediate[Cat], Intermediate[Dog]],
            relation_definition=WithProxy[
                Intermediate[Cat], Intermediate[Dog]
            ]._meta.fields["target"],
        ),
        PathSegment(
            type=Intermediate[Cat],
            relation_definition=Intermediate[Cat]._meta.fields["target"],
        ),
        PathSegment(type=Cat),
    ]

    assert paths[4] == [
        PathSegment(
            type=Event,
            relation_definition=Event._meta.fields["involves_entity"],
        ),
        PathSegment(
            type=WithProxy[Intermediate[Cat], Intermediate[Dog]],
            relation_definition=WithProxy[
                Intermediate[Cat], Intermediate[Dog]
            ]._meta.fields["proxy"],
        ),
        PathSegment(
            type=Intermediate[Dog],
            relation_definition=Intermediate[Dog]._meta.fields["target"],
        ),
        PathSegment(type=Dog),
    ]

    assert paths[5] == [
        PathSegment(type=Event, relation_definition=Event._meta.fields["involves_dog"]),
        PathSegment(type=Dog),
    ]

    assert paths[6] == [
        PathSegment(
            type=Event,
            relation_definition=Event._meta.fields["source"],
        ),
        PathSegment(
            type=Citation,
            relation_definition=Citation._meta.fields["cites"],
        ),
        PathSegment(type=Reference),
    ]

    assert paths[7] == [
        PathSegment(
            type=Event,
            relation_definition=Event._meta.fields["source"],
        ),
        PathSegment(
            type=Citation,
            relation_definition=Citation._meta.fields["cites_via_intermediate"],
        ),
        PathSegment(
            type=Intermediate[Reference],
            relation_definition=Intermediate[Reference]._meta.fields["target"],
        ),
        PathSegment(type=Reference),
    ]
