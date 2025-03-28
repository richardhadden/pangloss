from typing import Annotated

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
from pangloss.model_config.models_base import SemanticSpace, SemanticSpaceMeta
from pangloss.models import BaseNode, RelationConfig


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
