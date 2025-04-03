import datetime
from typing import Annotated, Optional, get_args, no_type_check

from pangloss import initialise_models
from pangloss.model_config.field_definitions import (
    RelationFieldDefinition,
    RelationToNodeDefinition,
    RelationToSemanticSpaceDefinition,
)
from pangloss.model_config.model_setup_functions.build_pg_model_definition import (
    build_field_definition,
)
from pangloss.model_config.model_setup_functions.build_semantic_space_meta import (
    initialise_semantic_space_meta_inheritance,
)
from pangloss.model_config.models_base import (
    BoundField,
    SemanticSpace,
    SemanticSpaceMeta,
)
from pangloss.models import BaseNode, RelationConfig
from pangloss.utils import gen_ulid


def test_semantic_space_meta_inheritance():
    class Negate[T](SemanticSpace[T]):
        """Creates a semantic space in which statements are negated"""

    class Infinitives[T](SemanticSpace[T]):
        """Abstract class for Infinitive and NegativeInfinitive types"""

        class Meta(SemanticSpaceMeta):
            abstract = True
            can_nest = False

    class Infinitive[T](Infinitives[T]):
        """Creates a semantic space in which contained statements have
        an infinitive (rather than indicative) character, e.g.
        an order *to do something* (rather than *something was done*)"""

    class NegativeInfinitive[T](Infinitives[T]):
        """Creates a semantic space in which contained statements have
        a negative infinitive (rather than indicative) character, e.g.
        an order *not to do something* (rather than *something was not done*)"""

    initialise_semantic_space_meta_inheritance(Infinitives)
    assert Infinitives._meta
    assert Infinitives._meta.abstract is True

    initialise_semantic_space_meta_inheritance(Infinitive)
    assert Infinitive._meta
    assert Infinitive._meta.abstract is False


def test_semantic_space_relation_definition():
    class Negate[T](SemanticSpace[T]):
        """Creates a semantic space in which statements are negated"""

    class Infinitives[T](SemanticSpace[T]):
        """Abstract class for Infinitive and NegativeInfinitive types"""

        class Meta(SemanticSpaceMeta):
            abstract = True

    class Infinitive[T: BaseNode](Infinitives[T]):
        """Creates a semantic space in which contained statements have
        an infinitive (rather than indicative) character, e.g.
        an order *to do something* (rather than *something was done*)"""

    class NegativeInfinitive[T: BaseNode](Infinitives[T]):
        """Creates a semantic space in which contained statements have
        a negative infinitive (rather than indicative) character, e.g.
        an order *not to do something* (rather than *something was not done*)"""

    class DoingThing(BaseNode):
        pass

    class Order(BaseNode):
        thing_ordered: Annotated[
            Infinitives[DoingThing],
            RelationConfig(reverse_name="was_ordered_not_to_be_done"),
        ]

    fd = build_field_definition(
        "thing_ordered",
        Annotated[
            Infinitives[DoingThing],
            RelationConfig(reverse_name="was_ordered_not_to_be_done"),
        ],
        Order,
    )

    assert isinstance(fd, RelationFieldDefinition)
    assert fd.field_name == "thing_ordered"
    assert fd.field_annotation == Infinitives[DoingThing]
    assert isinstance(fd.field_type_definitions[0], RelationToSemanticSpaceDefinition)
    assert fd.field_type_definitions[0].annotated_type == Infinitives[DoingThing]
    assert fd.field_type_definitions[0].origin_type is Infinitives
    assert fd.field_type_definitions[0].type_params_to_type_map["T"].type is DoingThing


def test_semantic_space_field_definition_of_bound_type():
    class Infinitives[T](SemanticSpace[T]):
        """Abstract class for Infinitive and NegativeInfinitive types"""

        class Meta(SemanticSpaceMeta):
            abstract = True

    class Infinitive[T: BaseNode](Infinitives[T]):
        """Creates a semantic space in which contained statements have
        an infinitive (rather than indicative) character, e.g.
        an order *to do something* (rather than *something was done*)"""

    class DoingThing(BaseNode):
        pass

    Infinitive[DoingThing]

    initialise_models()

    assert Infinitive._meta.fields
    assert Infinitive[DoingThing]._meta.fields
    assert Infinitive[DoingThing]._meta.fields != Infinitive._meta.fields

    contents_field_definition = Infinitive[DoingThing]._meta.fields["contents"]
    assert isinstance(contents_field_definition, RelationFieldDefinition)

    relation_type_defintion = contents_field_definition.field_type_definitions[0]
    assert isinstance(relation_type_defintion, RelationToNodeDefinition)
    assert relation_type_defintion.annotated_type is DoingThing


@no_type_check
def test_semanic_space_create_model():
    class Infinitives[T](SemanticSpace[T]):
        """Abstract class for Infinitive and NegativeInfinitive types"""

        class Meta(SemanticSpaceMeta):
            abstract = True

    class Infinitive[T: BaseNode](Infinitives[T]):
        """Creates a semantic space in which contained statements have
        an infinitive (rather than indicative) character, e.g.
        an order *to do something* (rather than *something was done*)"""

    class ReallyInfinitive[T: BaseNode](Infinitive[T]):
        """Creates a semantic space in which contained statements have
        an infinitive (rather than indicative) character, e.g.
        an order *to do something* (rather than *something was done*)"""

    class NegativeInfinitive[T](Infinitives[T]):
        pass

    class DoingThing(BaseNode):
        pass

    class DoingOtherThing(BaseNode):
        pass

    class Order(BaseNode):
        thing_ordered: Annotated[
            Infinitives[DoingThing | DoingOtherThing],
            RelationConfig(reverse_name="was_ordered_in"),
        ]

    initialise_models()

    assert (
        Order.Create.model_fields["thing_ordered"].annotation
        == list[
            Infinitive[DoingThing | DoingOtherThing].Create
            | ReallyInfinitive[DoingThing | DoingOtherThing].Create
            | NegativeInfinitive[DoingThing | DoingOtherThing].Create
        ]
    )

    assert (
        Infinitive[DoingThing | DoingOtherThing]
        .Create.model_fields["contents"]
        .annotation
        == list[DoingThing.Create | DoingOtherThing.Create]
    )

    order = Order(
        type="Order",
        label="An Order",
        thing_ordered=[
            {
                "type": "ReallyInfinitive",
                "contents": [{"type": "DoingThing", "label": "A Thing Done"}],
            }
        ],
    )

    assert order.thing_ordered[0].type == "ReallyInfinitive"
    assert order.thing_ordered[0].contents[0].type == "DoingThing"

    order = Order(
        type="Order",
        label="An Order",
        thing_ordered=[
            {
                "type": "Infinitive",
                "contents": [{"type": "DoingOtherThing", "label": "A Thing Done"}],
            }
        ],
    )

    assert order.thing_ordered[0].type == "Infinitive"
    assert order.thing_ordered[0].contents[0].type == "DoingOtherThing"


@no_type_check
def test_semanic_space_edit_set_model():
    class Infinitives[T](SemanticSpace[T]):
        """Abstract class for Infinitive and NegativeInfinitive types"""

        class Meta(SemanticSpaceMeta):
            abstract = True

    class Infinitive[T: BaseNode](Infinitives[T]):
        """Creates a semantic space in which contained statements have
        an infinitive (rather than indicative) character, e.g.
        an order *to do something* (rather than *something was done*)"""

    class ReallyInfinitive[T: BaseNode](Infinitive[T]):
        """Creates a semantic space in which contained statements have
        an infinitive (rather than indicative) character, e.g.
        an order *to do something* (rather than *something was done*)"""

    class NegativeInfinitive[T](Infinitives[T]):
        pass

    class DoingThing(BaseNode):
        pass

    class DoingOtherThing(BaseNode):
        pass

    class Order(BaseNode):
        thing_ordered: Annotated[
            Infinitives[DoingThing | DoingOtherThing],
            RelationConfig(reverse_name="was_ordered_in"),
        ]

    initialise_models()

    assert (
        Order.EditHeadSet.model_fields["thing_ordered"].annotation
        == list[
            ReallyInfinitive[DoingThing | DoingOtherThing].Create
            | ReallyInfinitive[DoingThing | DoingOtherThing].EditSet
            | Infinitive[DoingThing | DoingOtherThing].Create
            | Infinitive[DoingThing | DoingOtherThing].EditSet
            | NegativeInfinitive[DoingThing | DoingOtherThing].Create
            | NegativeInfinitive[DoingThing | DoingOtherThing].EditSet
        ]
    )

    order = Order.EditHeadSet(
        id=gen_ulid(),
        label="An Order",
        type="Order",
        thing_ordered=[
            {
                "id": gen_ulid(),
                "type": "Infinitive",
                "contents": [{"type": "DoingOtherThing", "label": "A Thing Done"}],
            }
        ],
    )


@no_type_check
def test_semanic_space_edit_view_model():
    class Infinitives[T](SemanticSpace[T]):
        """Abstract class for Infinitive and NegativeInfinitive types"""

        class Meta(SemanticSpaceMeta):
            abstract = True

    class Infinitive[T: BaseNode](Infinitives[T]):
        """Creates a semantic space in which contained statements have
        an infinitive (rather than indicative) character, e.g.
        an order *to do something* (rather than *something was done*)"""

    class ReallyInfinitive[T: BaseNode](Infinitive[T]):
        """Creates a semantic space in which contained statements have
        an infinitive (rather than indicative) character, e.g.
        an order *to do something* (rather than *something was done*)"""

    class NegativeInfinitive[T](Infinitives[T]):
        pass

    class DoingThing(BaseNode):
        pass

    class DoingOtherThing(BaseNode):
        pass

    class Order(BaseNode):
        thing_ordered: Annotated[
            Infinitives[DoingThing | DoingOtherThing],
            RelationConfig(reverse_name="was_ordered_in"),
        ]

    initialise_models()

    assert (
        Order.EditHeadView.model_fields["thing_ordered"].annotation
        == list[
            ReallyInfinitive[DoingThing | DoingOtherThing].View
            | Infinitive[DoingThing | DoingOtherThing].View
            | NegativeInfinitive[DoingThing | DoingOtherThing].View
        ]
    )

    order = Order.EditHeadView(
        id=gen_ulid(),
        label="An Order",
        type="Order",
        created_by="User",
        created_when=datetime.datetime.now(),
        thing_ordered=[
            {
                "id": gen_ulid(),
                "type": "Infinitive",
                "contents": [
                    {
                        "type": "DoingOtherThing",
                        "label": "A Thing Done",
                        "id": gen_ulid(),
                    }
                ],
            }
        ],
    )

    assert order.thing_ordered[0].type == "Infinitive"
    assert order.thing_ordered[0].contents[0].type == "DoingOtherThing"


@no_type_check
def test_semanic_space_view_model():
    class Infinitives[T](SemanticSpace[T]):
        """Abstract class for Infinitive and NegativeInfinitive types"""

        class Meta(SemanticSpaceMeta):
            abstract = True

    class Infinitive[T: BaseNode](Infinitives[T]):
        """Creates a semantic space in which contained statements have
        an infinitive (rather than indicative) character, e.g.
        an order *to do something* (rather than *something was done*)"""

    class ReallyInfinitive[T: BaseNode](Infinitive[T]):
        """Creates a semantic space in which contained statements have
        an infinitive (rather than indicative) character, e.g.
        an order *to do something* (rather than *something was done*)"""

    class NegativeInfinitive[T](Infinitives[T]):
        pass

    class DoingThing(BaseNode):
        pass

    class DoingOtherThing(BaseNode):
        pass

    class Order(BaseNode):
        thing_ordered: Annotated[
            Infinitives[DoingThing | DoingOtherThing],
            RelationConfig(reverse_name="was_ordered_in"),
        ]

    initialise_models()

    assert (
        Order.HeadView.model_fields["thing_ordered"].annotation
        == list[
            ReallyInfinitive[DoingThing | DoingOtherThing].View
            | Infinitive[DoingThing | DoingOtherThing].View
            | NegativeInfinitive[DoingThing | DoingOtherThing].View
        ]
    )

    order = Order.HeadView(
        id=gen_ulid(),
        label="An Order",
        type="Order",
        created_by="User",
        created_when=datetime.datetime.now(),
        thing_ordered=[
            {
                "id": gen_ulid(),
                "type": "Infinitive",
                "contents": [
                    {
                        "type": "DoingOtherThing",
                        "label": "A Thing Done",
                        "id": gen_ulid(),
                    }
                ],
            }
        ],
    )

    assert order.thing_ordered[0].type == "Infinitive"
    assert order.thing_ordered[0].contents[0].type == "DoingOtherThing"


@no_type_check
def test_bound_field_through_semantic_space():
    class Infinitives[T](SemanticSpace[T]):
        """Abstract class for Infinitive and NegativeInfinitive types"""

        class Meta(SemanticSpaceMeta):
            abstract = True

    class Infinitive[T: BaseNode](Infinitives[T]):
        """Creates a semantic space in which contained statements have
        an infinitive (rather than indicative) character, e.g.
        an order *to do something* (rather than *something was done*)"""

    class Person(BaseNode):
        pass

    class DoingThing(BaseNode):
        done_by_person: Annotated[Person, RelationConfig(reverse_name="did_a_thing")]

    class Order(BaseNode):
        person_receiving_order: Annotated[
            Person, RelationConfig(reverse_name="received_an_order")
        ]
        thing_ordered: Annotated[
            Infinitives[DoingThing],
            RelationConfig(
                reverse_name="was_ordered_in",
                create_inline=True,
                bind_fields_to_related=[
                    BoundField("person_receiving_order", "done_by_person")
                ],
            ),
        ]

    initialise_models()

    assert (
        Infinitive[DoingThing]
        .Create.in_context_of.Order.thing_ordered.model_fields["contents"]
        .annotation
        == list[DoingThing.Create.in_context_of.Order.thing_ordered]
    )

    assert (
        get_args(
            Infinitive[DoingThing]
            .Create.in_context_of.Order.thing_ordered.model_fields["contents"]
            .annotation
        )[0]
        == DoingThing.Create.in_context_of.Order.thing_ordered
    )

    assert (
        DoingThing.Create.in_context_of.Order.thing_ordered.model_fields[
            "done_by_person"
        ].annotation
        == Optional[list[Person.ReferenceSet]]
    )
