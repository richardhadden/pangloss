import datetime
from typing import Annotated, no_type_check

from pangloss_new import initialise_models
from pangloss_new.model_config.models_base import (
    EdgeModel,
    Embedded,
    HeritableTrait,
    ReifiedRelation,
    RelationConfig,
)
from pangloss_new.models import BaseNode
from pangloss_new.utils import gen_ulid


@no_type_check
def test_head_view_model_with_collapsible_reified():
    class Certainty(EdgeModel):
        certainty: int

    class Identification[T](ReifiedRelation[T]):
        target: Annotated[
            T, RelationConfig(reverse_name="is_target_of", edge_model=Certainty)
        ]

        def collapse_when(self: "Identification") -> bool:
            if len(self.target) == 1 and self.target[0].edge_properties.certainty == 1:
                return True
            return False

    class Person(BaseNode):
        pass

    class Event(BaseNode):
        involves_person: Annotated[
            Identification[Person],
            RelationConfig(reverse_name="is_involved_in"),
        ]

    initialise_models()

    e = Event.EditHeadView(
        type="Event",
        id=gen_ulid(),
        label="An Event",
        urls=[],
        created_by="Smith",
        created_when=datetime.datetime.now(),
        modified_by="Smith",
        modified_when=datetime.datetime.now(),
        involves_person=[
            {
                "type": "Identification",
                "id": gen_ulid(),
                "target": [
                    {
                        "type": "Person",
                        "id": gen_ulid(),
                        "label": "A Second Person",
                        "edge_properties": {"certainty": 0},
                    }
                ],
            },
        ],
    )

    assert e.involves_person[0].collapsed is False

    # Now test again with certainty==1 to check for collapse of Identification
    e = Event.EditHeadView(
        type="Event",
        id=gen_ulid(),
        label="An Event",
        urls=[],
        created_by="Smith",
        created_when=datetime.datetime.now(),
        modified_by="Smith",
        modified_when=datetime.datetime.now(),
        involves_person=[
            {
                "type": "Identification",
                "id": gen_ulid(),
                "target": [
                    {
                        "type": "Person",
                        "id": gen_ulid(),
                        "label": "A Second Person",
                        "edge_properties": {"certainty": 1},
                    }
                ],
            },
        ],
    )
    assert e.involves_person[0].collapsed is True


@no_type_check
def test_reverse_relation_simple_direct_on_head_view_model():
    class Dog(BaseNode):
        pass

    class Cat(BaseNode):
        pass

    class Event(BaseNode):
        involves_cat: Annotated[
            Cat,
            RelationConfig(reverse_name="is_involved_in"),
        ]
        involves_dog: Annotated[Dog, RelationConfig(reverse_name="is_involved_in")]

    class Party(BaseNode):
        involves_cat: Annotated[
            Cat,
            RelationConfig(reverse_name="is_involved_in"),
        ]

    initialise_models()

    assert (
        Cat.HeadView.model_fields["is_involved_in"].annotation
        == list[Event.ReferenceView | Party.ReferenceView]
    )

    assert (
        Dog.HeadView.model_fields["is_involved_in"].annotation
        == list[Event.ReferenceView]
    )

    # Test initialise if no data for is_involved_in
    cat1 = Cat.HeadView(
        type="Cat",
        id=gen_ulid(),
        label="My Cat",
        created_by="Smith",
        created_when=datetime.datetime.now(),
        modified_by="Smith",
        modified_when=datetime.datetime.now(),
    )

    assert cat1.is_involved_in == []

    # Test initialise with data for is_involved_in
    cat2 = Cat.HeadView(
        type="Cat",
        id=gen_ulid(),
        label="My Cat",
        created_by="Smith",
        created_when=datetime.datetime.now(),
        modified_by="Smith",
        modified_when=datetime.datetime.now(),
        is_involved_in=[{"type": "Event", "id": gen_ulid(), "label": "An Event"}],
    )

    assert isinstance(cat2.is_involved_in[0], Event.ReferenceView)
    assert cat2.is_involved_in[0].label == "An Event"


@no_type_check
def test_reverse_relation_direct_with_edge_properties_on_head_view_model():
    class Certainty(EdgeModel):
        certainty: int

    class Cat(BaseNode):
        pass

    class Event(BaseNode):
        involves_cat: Annotated[
            Cat,
            RelationConfig(reverse_name="is_involved_in", edge_model=Certainty),
        ]

    initialise_models()

    assert (
        Cat.HeadView.model_fields["is_involved_in"].annotation
        == list[Event.ReferenceView.via.Certainty]
    )

    cat2 = Cat.HeadView(
        type="Cat",
        id=gen_ulid(),
        label="My Cat",
        created_by="Smith",
        created_when=datetime.datetime.now(),
        modified_by="Smith",
        modified_when=datetime.datetime.now(),
        is_involved_in=[
            {
                "type": "Event",
                "id": gen_ulid(),
                "label": "An Event",
                "edge_properties": {"certainty": 1},
            }
        ],
    )

    assert isinstance(cat2.is_involved_in[0], Event.ReferenceView.via.Certainty)
    assert cat2.is_involved_in[0].label == "An Event"
    assert cat2.is_involved_in[0].edge_properties.certainty == 1


@no_type_check
def test_reverse_relation_to_trait():
    class Animalian(HeritableTrait):
        pass

    class Dog(BaseNode, Animalian):
        pass

    class Cat(BaseNode, Animalian):
        pass

    class Event(BaseNode):
        involves_cat: Annotated[
            Animalian,
            RelationConfig(reverse_name="is_involved_in"),
        ]

    initialise_models()

    assert (
        Dog.HeadView.model_fields["is_involved_in"].annotation
        == list[Event.ReferenceView]
    )

    assert (
        Cat.HeadView.model_fields["is_involved_in"].annotation
        == list[Event.ReferenceView]
    )


@no_type_check
def test_reverse_relation_to_contextual_model():
    class Dog(BaseNode):
        pass

    class Cat(BaseNode):
        pass

    class Intermediate[T](ReifiedRelation[T]):
        pass

    class Event(BaseNode):
        involves_entity: Annotated[
            Cat | Intermediate[Cat] | Dog,
            RelationConfig(reverse_name="is_involved_in_event"),
        ]

    initialise_models()
    # print(Event.View.in_context_of.Cat.is_involved_in_event)

    assert (
        Cat.HeadView.model_fields["is_involved_in_event"].annotation
        == list[Event.ReferenceView | Event.View.in_context_of.Cat.is_involved_in_event]
    )

    event_view_in_context = Event.View.in_context_of.Cat.is_involved_in_event
    assert "involves_entity" in event_view_in_context.model_fields.keys()

    assert (
        event_view_in_context.model_fields["involves_entity"].annotation
        == list[Intermediate[Cat].View]
    )

    cat1 = Cat.HeadView(
        type="Cat",
        id=gen_ulid(),
        label="My Cat",
        created_by="Smith",
        created_when=datetime.datetime.now(),
        modified_by="Smith",
        modified_when=datetime.datetime.now(),
        is_involved_in_event=[
            {"type": "Event", "id": gen_ulid(), "label": "Event One"}
        ],
    )

    assert isinstance(cat1.is_involved_in_event[0], Event.ReferenceView)

    cat2 = Cat.HeadView(
        type="Cat",
        id=gen_ulid(),
        label="My Cat",
        created_by="Smith",
        created_when=datetime.datetime.now(),
        modified_by="Smith",
        modified_when=datetime.datetime.now(),
        is_involved_in_event=[
            {
                "type": "Event",
                "id": gen_ulid(),
                "label": "Event One",
                "involves_entity": [
                    {
                        "type": "Intermediate",
                        "id": gen_ulid(),
                        "target": [
                            {"type": "Cat", "id": gen_ulid(), "label": "My Cat"}
                        ],
                    }
                ],
            }
        ],
    )

    assert cat2.is_involved_in_event[0].type == "Event"
    assert isinstance(
        cat2.is_involved_in_event[0],
        Event.View.in_context_of.Cat.is_involved_in_event,
    )
    assert cat2.is_involved_in_event[0].involves_entity[0].type == "Intermediate"
    assert isinstance(
        cat2.is_involved_in_event[0].involves_entity[0], Intermediate[Cat].View
    )
    assert cat2.is_involved_in_event[0].involves_entity[0].target[0].type == "Cat"
    assert isinstance(
        cat2.is_involved_in_event[0].involves_entity[0].target[0], Cat.ReferenceView
    )


@no_type_check
def test_reverse_relation_on_direct_to_embedded():
    class Reference(BaseNode):
        pass

    class Citation(BaseNode):
        cites: Annotated[Reference, RelationConfig(reverse_name="is_cited_in")]

    class Factoid(BaseNode):
        source: Embedded[Citation]

    initialise_models()

    assert Reference._meta.reverse_relations["is_cited_in"].pop() == ""
