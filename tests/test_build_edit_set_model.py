"""
EditSet model should
- allow either Create or EditSet for any list types

"""

from typing import Annotated, Union, get_args, get_origin, no_type_check

from pangloss_new import initialise_models
from pangloss_new.model_config.models_base import (
    BaseMeta,
    EdgeModel,
    ReifiedRelation,
    RelationConfig,
)
from pangloss_new.models import BaseNode
from pangloss_new.utils import gen_ulid


@no_type_check
def test_build_edit_head_set_model():
    class Person(BaseNode):
        pass

    class Statement(BaseNode):
        involves_person: Annotated[
            Person,
            RelationConfig(reverse_name="is_involved_in"),
        ]
        has_substatements: Annotated[
            "Statement",
            RelationConfig(
                reverse_name="is_substatement_of", create_inline=True, edit_inline=True
            ),
        ]

    class Declaration(Statement):
        pass

    class Factoid(BaseNode):
        has_statements: Annotated[
            Statement,
            RelationConfig(
                reverse_name="is_statement_in", create_inline=True, edit_inline=True
            ),
        ]

    initialise_models()

    assert Factoid.EditHeadSet
    assert (
        Factoid.EditHeadSet.model_fields["has_statements"].annotation
        == list[
            Statement.Create
            | Statement.EditSet
            | Declaration.Create
            | Declaration.EditSet
        ]
    )

    assert (
        Statement.EditSet.model_fields["has_substatements"].annotation
        == list[
            Statement.Create
            | Statement.EditSet
            | Declaration.Create
            | Declaration.EditSet
        ]
    )

    assert (
        Statement.EditSet.model_fields["involves_person"].annotation
        == list[Person.ReferenceSet]
    )

    f = Factoid.EditHeadSet(
        id=gen_ulid(),
        type="Factoid",
        label="A Factoid",
        has_statements=[
            {
                "type": "Statement",
                "label": "A New Statement",
                "involves_person": [
                    {
                        "type": "Person",
                        "label": "A Person",
                        "id": gen_ulid(),
                    }
                ],
                "has_substatements": [],
            },
            {
                "type": "Statement",
                "label": "Existing Statement",
                "id": gen_ulid(),
                "involves_person": [
                    {
                        "type": "Person",
                        "label": "A Person",
                        "id": gen_ulid(),
                    }
                ],
                "has_substatements": [],
            },
            {
                "type": "Declaration",
                "label": "A New Declaration",
                "involves_person": [
                    {
                        "type": "Person",
                        "label": "A Person",
                        "id": gen_ulid(),
                    }
                ],
                "has_substatements": [],
            },
            {
                "type": "Declaration",
                "label": "Existing Declaration",
                "id": gen_ulid(),
                "involves_person": [
                    {
                        "type": "Person",
                        "label": "A Person",
                        "id": gen_ulid(),
                    }
                ],
                "has_substatements": [],
            },
        ],
    )

    assert f.type == "Factoid"
    assert f.label == "A Factoid"
    assert f.id is not None
    assert isinstance(f.has_statements[0], Statement.Create)
    assert isinstance(f.has_statements[1], Statement.EditSet)
    assert isinstance(f.has_statements[2], Declaration.Create)
    assert isinstance(f.has_statements[3], Declaration.EditSet)

    assert f.has_statements[0].type == "Statement"
    assert f.has_statements[0].label == "A New Statement"
    assert not f.has_statements[0].id
    assert isinstance(f.has_statements[0].involves_person[0], Person.ReferenceSet)
    assert not hasattr(f.has_statements[0].involves_person[0], "label")

    assert f.has_statements[1].type == "Statement"
    assert f.has_statements[1].label == "Existing Statement"
    assert isinstance(f.has_statements[1].involves_person[0], Person.ReferenceSet)

    assert f.has_statements[2].type == "Declaration"
    assert f.has_statements[3].type == "Declaration"


@no_type_check
def test_build_edit_set_model_with_complex_options():
    class Person(BaseNode):
        pass

    class Dude(Person):
        class Meta(BaseMeta):
            create_by_reference = True

    class Animal(BaseNode):
        class Meta(BaseMeta):
            abstract = True

    class Cat(Animal):
        pass

    class Statement(BaseNode):
        involves_being: Annotated[
            Person | Animal,
            RelationConfig(reverse_name="is_involved_in"),
        ]
        has_substatements: Annotated[
            "Statement",
            RelationConfig(
                reverse_name="is_substatement_of", create_inline=True, edit_inline=True
            ),
        ]

    class Declaration(Statement):
        pass

    class Factoid(BaseNode):
        has_statements: Annotated[
            Statement,
            RelationConfig(
                reverse_name="is_statement_in", create_inline=True, edit_inline=True
            ),
        ]

    initialise_models()

    assert (
        Statement.EditSet.model_fields["involves_being"].annotation
        == list[
            Dude.ReferenceCreate
            | Dude.ReferenceSet
            | Person.ReferenceSet
            | Cat.ReferenceSet
        ]
    )

    f = Factoid.EditHeadSet(
        id=gen_ulid(),
        label="A Factoid",
        has_statements=[
            {
                "type": "Statement",
                "id": gen_ulid(),
                "label": "A Statement",
                "involves_being": [
                    {"type": "Dude", "label": "A dude", "id": gen_ulid()},
                    {"type": "Dude", "id": gen_ulid()},
                    {"type": "Person", "label": "a person", "id": gen_ulid()},
                    {"type": "Cat", "label": "A Cat", "id": gen_ulid()},
                ],
                "has_substatements": [],
            }
        ],
    )

    assert isinstance(f.has_statements[0].involves_being[0], Dude.ReferenceCreate)
    assert isinstance(f.has_statements[0].involves_being[1], Dude.ReferenceSet)
    assert isinstance(f.has_statements[0].involves_being[2], Person.ReferenceSet)
    assert isinstance(f.has_statements[0].involves_being[3], Cat.ReferenceSet)


@no_type_check
def test_build_edit_set_model_with_reified_relations():
    class Intermediate[T](ReifiedRelation[T]):
        pass

    class Person(BaseNode):
        pass

    class Certainty(EdgeModel):
        certainty: int

    class Event(BaseNode):
        involves_person: Annotated[
            Intermediate[Person] | Person,
            RelationConfig(reverse_name="is_involved_in", edge_model=Certainty),
        ]

    initialise_models()

    assert (
        get_origin(Event.EditHeadSet.model_fields["involves_person"].annotation) is list
    )
    union = get_args(Event.EditHeadSet.model_fields["involves_person"].annotation)[0]
    assert get_origin(union) is Union
    assert get_args(union)[0] == Person.ReferenceSet.via.Certainty
    assert get_args(union)[1] == Intermediate[Person].EditSet.via.Certainty
    assert get_args(union)[2] == Intermediate[Person].Create.via.Certainty

    e = Event.EditHeadSet(
        id=gen_ulid(),
        label="An Event",
        involves_person=[
            {"type": "Person", "id": gen_ulid(), "edge_properties": {"certainty": 1}},
            {
                "type": "Intermediate",
                "id": gen_ulid(),
                "edge_properties": {"certainty": 1},
                "target": [{"type": "Person", "id": gen_ulid()}],
            },
            {
                "type": "Intermediate",
                "edge_properties": {"certainty": 1},
                "target": [{"type": "Person", "id": gen_ulid()}],
            },
        ],
    )

    assert isinstance(e.involves_person[0], Person.ReferenceSet)
    assert isinstance(e.involves_person[0], Person.ReferenceSet.via.Certainty)

    assert isinstance(e.involves_person[1], Intermediate[Person].EditSet)
    assert isinstance(e.involves_person[1], Intermediate[Person].EditSet.via.Certainty)

    assert isinstance(e.involves_person[2], Intermediate[Person].Create)
    assert isinstance(e.involves_person[2], Intermediate[Person].Create.via.Certainty)
