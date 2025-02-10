import typing

import annotated_types
import pytest

from pangloss_new.exceptions import PanglossConfigError
from pangloss_new.model_config.field_definitions import (
    RelationDefinition,
    RelationFieldDefinition,
    RelationToReifiedDefinition,
)
from pangloss_new.model_config.model_manager import ModelManager
from pangloss_new.model_config.model_setup_functions.build_pg_model_definition import (
    build_field_definition,
)
from pangloss_new.models import BaseNode, ReifiedRelation, RelationConfig


def test_model_annotations():
    """Should set __pg_annotations__ to a ChainMap of dicts representing
    the annotations objects for class and its parents"""

    class Official(BaseNode):
        department: str

    class Human(BaseNode):
        age: int
        department: int

    class PoliceOfficer(Human, Official):
        rank: str

    ModelManager.initialise_models(_defined_in_test=True)

    assert PoliceOfficer.__pg_annotations__["rank"] is str
    assert PoliceOfficer.__pg_annotations__["age"] is int
    assert PoliceOfficer.__pg_annotations__["department"] is int


def test_literal_type_set_on_model():
    class Official(BaseNode):
        pass

    class Human(BaseNode):
        pass

    class PoliceOfficer(Human, Official):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert Official.type == "Official"
    assert Human.type == "Human"
    assert PoliceOfficer.type == "PoliceOfficer"


def test_register_reified_relation_model():
    class Intermediate[T](ReifiedRelation[T]):
        pass

    class Cat(BaseNode):
        pass

    class Person(BaseNode):
        related_via_intermediate: typing.Annotated[
            Intermediate[Cat],
            RelationConfig(reverse_name="reverse_related_via_intermeidate"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert ModelManager.reified_relation_models == {"Intermediate": Intermediate}


def test_literal_type_set_on_reified_relation():
    class Intermediate[T](ReifiedRelation[T]):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert Intermediate.type == "Intermediate"


def test_reified_relation_types_can_have_additional_type_params():
    class Cat(BaseNode):
        pass

    class Dog(BaseNode):
        pass

    class Intermediate[T, U](ReifiedRelation[T]):
        other: U

    ModelManager.initialise_models(_defined_in_test=True)

    Intermediate[Cat, Dog]


def test_create_field_definition_with_basic_relation():
    class Cat(BaseNode):
        pass

    class Person(BaseNode):
        pass

    # Test we can annotate with related to basic type
    rel_to_basic_field_definition = build_field_definition(
        "related",
        typing.Annotated[
            Cat,
            RelationConfig(
                reverse_name="reverse_related", validators=[annotated_types.MinLen(1)]
            ),
            annotated_types.MaxLen(2),
        ],
        Person,
    )
    assert isinstance(rel_to_basic_field_definition, RelationFieldDefinition)
    assert rel_to_basic_field_definition.field_annotation is Cat
    assert isinstance(
        rel_to_basic_field_definition.field_type_definitions[0], RelationDefinition
    )
    assert rel_to_basic_field_definition.field_type_definitions[0].annotated_type is Cat
    assert rel_to_basic_field_definition.reverse_name == "reverse_related"

    assert rel_to_basic_field_definition.validators == [
        annotated_types.MinLen(1),
        annotated_types.MaxLen(2),
    ]


def test_create_field_definition_raises_error_with_mix_of_relation_and_property_types():
    class Person(BaseNode):
        pass

    class Cat(BaseNode):
        pass

    # Test build_field_definition fails with a union of relation and builtin types
    with pytest.raises(PanglossConfigError):
        build_field_definition(
            "related_to_union_fail",
            typing.Annotated[Cat | str, RelationConfig(reverse_name="reverse_related")],
            Person,
        )


def test_relation_via_intermediate_builds_field_definition():
    class Intermediate[T](ReifiedRelation[T]):
        pass

    class Cat(BaseNode):
        pass

    class Person(BaseNode):
        pass

    # Test relation via intermediate returns a field definition
    # with a RelationToReifiedDefinition
    rel_via_intermediate_field_definition = build_field_definition(
        "related_via_intermediate",
        typing.Annotated[
            Intermediate[Cat],
            RelationConfig(reverse_name="reverse_related_via_intermediate"),
        ],
        Person,
    )

    assert isinstance(rel_via_intermediate_field_definition, RelationFieldDefinition)
    assert rel_via_intermediate_field_definition.field_annotation is Intermediate[Cat]
    assert isinstance(
        rel_via_intermediate_field_definition.field_type_definitions[0],
        RelationToReifiedDefinition,
    )
    assert (
        rel_via_intermediate_field_definition.field_type_definitions[0].annotated_type
        is Intermediate[Cat]
    )
    assert (
        rel_via_intermediate_field_definition.field_type_definitions[0].origin_type
        is Intermediate
    )

    T = (
        rel_via_intermediate_field_definition.field_type_definitions[0]
        .type_params_to_type_map["T"]
        .type_param
    )
    assert isinstance(
        T,
        typing.TypeVar,
    )

    V = (
        rel_via_intermediate_field_definition.field_type_definitions[0]
        .type_params_to_type_map["T"]
        .type
    )
    assert V is Cat


def test_create_relation_field_with_relation_to_union():
    class Intermediate[T](ReifiedRelation[T]):
        pass

    class Cat(BaseNode):
        pass

    class Dog(BaseNode):
        pass

    class Person(BaseNode):
        pass

    rel_to_union_field_definition = build_field_definition(
        "relation_to_union",
        typing.Annotated[
            Cat | Dog | Intermediate[Cat],
            RelationConfig(reverse_name="reverse_relation_to_union"),
        ],
        Person,
    )

    assert rel_to_union_field_definition
    assert isinstance(rel_to_union_field_definition, RelationFieldDefinition)
    assert rel_to_union_field_definition.field_type_definitions[0].annotated_type is Cat
    assert rel_to_union_field_definition.field_type_definitions[1].annotated_type is Dog

    assert isinstance(
        rel_to_union_field_definition.field_type_definitions[2],
        RelationToReifiedDefinition,
    )
    assert (
        rel_to_union_field_definition.field_type_definitions[2].annotated_type
        is Intermediate[Cat]
    )
    assert (
        rel_to_union_field_definition.field_type_definitions[2].origin_type
        is Intermediate
    )
    assert (
        rel_to_union_field_definition.field_type_definitions[2]
        .type_params_to_type_map["T"]
        .type
        is Cat
    )


def test_create_relation_field_with_relation_to_union_defined_with_typing_union():
    class Intermediate[T](ReifiedRelation[T]):
        pass

    class Cat(BaseNode):
        pass

    class Dog(BaseNode):
        pass

    class Person(BaseNode):
        pass

    rel_to_union_field_definition = build_field_definition(
        "relation_to_union",
        typing.Annotated[
            typing.Union[Cat, Dog, Intermediate[Cat]],
            RelationConfig(reverse_name="reverse_relation_to_union"),
        ],
        Person,
    )

    assert rel_to_union_field_definition
    assert isinstance(rel_to_union_field_definition, RelationFieldDefinition)
    assert rel_to_union_field_definition.field_type_definitions[0].annotated_type is Cat

    assert rel_to_union_field_definition.field_type_definitions[1].annotated_type is Dog

    assert isinstance(
        rel_to_union_field_definition.field_type_definitions[2],
        RelationToReifiedDefinition,
    )
    assert (
        rel_to_union_field_definition.field_type_definitions[2].annotated_type
        is Intermediate[Cat]
    )
    assert (
        rel_to_union_field_definition.field_type_definitions[2].origin_type
        is Intermediate
    )
    assert (
        rel_to_union_field_definition.field_type_definitions[2]
        .type_params_to_type_map["T"]
        .type
        is Cat
    )


def test_create_relation_field_to_reified_with_union_of_types():
    class Intermediate[T](ReifiedRelation[T]):
        pass

    class Cat(BaseNode):
        pass

    class Dog(BaseNode):
        pass

    class Person(BaseNode):
        pass

    rel_to_reified_union_field_definition = build_field_definition(
        "relation_to_union",
        typing.Annotated[
            Intermediate[Cat | Dog] | Cat,
            RelationConfig(reverse_name="reverse_relation_to_union"),
        ],
        Person,
    )

    assert rel_to_reified_union_field_definition
    assert isinstance(rel_to_reified_union_field_definition, RelationFieldDefinition)
    assert isinstance(
        rel_to_reified_union_field_definition.field_type_definitions[0],
        RelationToReifiedDefinition,
    )
    assert (
        rel_to_reified_union_field_definition.field_type_definitions[0].annotated_type
        is Intermediate[Cat | Dog]
    )
    assert (
        rel_to_reified_union_field_definition.field_type_definitions[0].origin_type
        is Intermediate
    )
    assert (
        rel_to_reified_union_field_definition.field_type_definitions[0]
        .type_params_to_type_map["T"]
        .type
        == Cat | Dog
    )


def test_build_create_model():
    from pydantic import BaseModel

    class Intermediate[T](ReifiedRelation[T]):
        pass

    class Thing(BaseModel):
        pass

    class Event(BaseNode):
        done_by: typing.Annotated[
            Intermediate[Thing], RelationConfig(reverse_name="did")
        ]

    Intermediate[Thing](type="Thing", target=Thing())

    assert False
