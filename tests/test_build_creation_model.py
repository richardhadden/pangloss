from typing import Annotated, Union, get_args, get_origin, no_type_check

from annotated_types import Gt

from pangloss_new import initialise_models
from pangloss_new.model_config.model_manager import ModelManager
from pangloss_new.model_config.models_base import BaseMeta, EdgeModel, RelationConfig
from pangloss_new.models import BaseNode, ReifiedRelation
from pangloss_new.utils import gen_ulid


@no_type_check
def test_build_creation_model_basic():
    class Person(BaseNode):
        age: Annotated[int, Gt(1)]

    ModelManager.initialise_models()

    assert Person.Create
    assert Person.Create.__pg_base_class__ is Person
    assert Person.Create.model_fields["age"].metadata == [Gt(1)]

    john_smith = Person(
        label="John Smith",
        age="2",
    )

    assert john_smith.type == "Person"
    assert john_smith.label == "John Smith"
    assert john_smith.age == 2


@no_type_check
def test_create_model_with_relations():
    class Cat(BaseNode):
        pass

    class NiceCat(Cat):
        class Meta(BaseMeta):
            create_by_reference = True

    class Person(BaseNode):
        age: Annotated[int, Gt(1)]
        owns_cat: Annotated[Cat, RelationConfig(reverse_name="is_owned_by")]

    ModelManager.initialise_models()

    assert Person.Create
    assert Cat.Create
    assert NiceCat.Create

    Cat(label="Mister Fluffy")
    NiceCat(label="Mr Very Fluffy")

    john_smith = Person(
        label="John Smith",
        age="2",
        owns_cat=[
            {"type": "Cat", "id": gen_ulid()},
            {"type": "NiceCat", "id": gen_ulid()},
            {"type": "NiceCat", "id": gen_ulid(), "label": "A New Cat"},
        ],
    )

    assert john_smith.owns_cat[0].type == "Cat"
    assert isinstance(john_smith.owns_cat[0], Cat.ReferenceSet)

    assert john_smith.owns_cat[1].type == "NiceCat"
    assert isinstance(john_smith.owns_cat[1], NiceCat.ReferenceSet)

    assert john_smith.owns_cat[2].type == "NiceCat"
    assert john_smith.owns_cat[2].label == "A New Cat"
    assert isinstance(john_smith.owns_cat[2], NiceCat.ReferenceCreate)


@no_type_check
def test_create_model_with_reified_relations():
    class Identification[T](ReifiedRelation[T]):
        pass

    class Cat(BaseNode):
        pass

    class Person(BaseNode):
        owns_cat: Annotated[
            Identification[Cat],
            RelationConfig(reverse_name="is_owned_by"),
        ]

    initialise_models()

    assert (
        Person.Create.model_fields["owns_cat"].annotation
        == list[Identification[Cat].Create]
    )

    person = Person(
        label="John Smith",
        owns_cat=[
            {"type": "Identification", "target": [{"type": "Cat", "id": gen_ulid()}]}
        ],
    )
    assert person.type == "Person"
    assert person.owns_cat[0].type == "Identification"
    assert person.owns_cat[0].target[0].type == "Cat"


@no_type_check
def test_create_model_with_double_reified_relations():
    class Intermediate[T, U](ReifiedRelation[T]):
        other: Annotated[U, RelationConfig(reverse_name="is_other_in")]

    class Identification[T](ReifiedRelation[T]):
        pass

    class Cat(BaseNode):
        pass

    class Dog(BaseNode):
        pass

    class Person(BaseNode):
        owns_cat: Annotated[
            Intermediate[Identification[Cat], Identification[Dog]]
            | Identification[Cat]
            | Cat,
            RelationConfig(reverse_name="is_owned_by"),
        ]

    initialise_models()

    assert (
        Person.Create.model_fields["owns_cat"].annotation
        == list[
            Union[
                Intermediate[Identification[Cat], Identification[Dog]].Create,
                Identification[Cat].Create,
                Cat.ReferenceSet,
            ]
        ]
    )

    assert (
        Intermediate[Identification[Cat], Identification[Dog]]
        .Create.model_fields["target"]
        .annotation
        == list[Identification[Cat].Create]
    )

    assert (
        Identification[Cat].Create.model_fields["target"].annotation
        == list[Cat.ReferenceSet]
    )


def test_build_create_model_with_edge_model():
    class Edge(EdgeModel):
        value: int

    class Edge2(EdgeModel):
        value: int

    class Intermediate[T](ReifiedRelation[T]):
        target: Annotated[
            T, RelationConfig(reverse_name="is_target_of", edge_model=Edge2)
        ]

    class Cat(BaseNode):
        class Meta(BaseMeta):
            create_by_reference = True

    class Dog(BaseNode):
        pass

    class Person(BaseNode):
        owns_cat: Annotated[
            Cat | Dog | Intermediate[Dog],
            RelationConfig(reverse_name="is_owned_by", edge_model=Edge),
        ]

    initialise_models()

    annotation = Person.Create.model_fields["owns_cat"].annotation

    assert get_origin(annotation) is list
    assert get_origin(get_args(annotation)[0]) is Union
    inner_args = get_args(get_args(annotation)[0])

    assert inner_args[0].__name__ == "CatReferenceSet__via__Edge"
    assert inner_args[0] is Cat.ReferenceSet.via.Edge

    assert inner_args[1].__name__ == "CatReferenceCreate__via__Edge"

    assert Cat.ReferenceCreate
    assert inner_args[1] is Cat.ReferenceCreate.via.Edge

    assert inner_args[2].__name__ == "DogReferenceSet__via__Edge"
    assert inner_args[2] is Dog.ReferenceSet.via.Edge

    assert inner_args[3].__name__ == "Intermediate[Dog]Create__via__Edge"
    assert inner_args[3] is Intermediate[Dog].Create.via.Edge

    assert get_origin(inner_args[3].model_fields["target"].annotation) is list
    assert (
        get_args(inner_args[3].model_fields["target"].annotation)[0].__name__
        == "DogReferenceSet__via__Edge2"
    )

    assert (
        get_args(inner_args[3].model_fields["target"].annotation)[0]
        is Dog.ReferenceSet.via.Edge2
    )
