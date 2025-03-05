from typing import Annotated

import pytest

from pangloss_new import initialise_models
from pangloss_new.exceptions import PanglossConfigError
from pangloss_new.models import BaseNode, RelationConfig
from pangloss_new.utils import gen_ulid


def test_override_inherited_relations_in_model_fields():
    class Task(BaseNode):
        pass

    class Agent(BaseNode):
        does_thing: Annotated[Task, RelationConfig(reverse_name="is_done_by")]

    class Person(Agent):
        person_does_thing: Annotated[
            Task,
            RelationConfig(
                reverse_name="is_done_by_person", subclasses_relation=["does_thing"]
            ),
        ]

    class Dude(Person):
        dude_does_thing: Annotated[
            Task,
            RelationConfig(
                reverse_name="is_done_by_dude",
                subclasses_relation=["person_does_thing"],
            ),
        ]

    initialise_models()

    assert "does_thing" in Agent._meta.fields
    agent_does_thing_definition = Agent._meta.fields.relation_fields["does_thing"]
    assert agent_does_thing_definition
    assert "does_thing" in agent_does_thing_definition.relation_labels
    assert "is_done_by" in agent_does_thing_definition.reverse_relation_labels

    assert "does_thing" not in Person._meta.fields
    assert "person_does_thing" in Person._meta.fields
    person_does_thing_definition = Person._meta.fields.relation_fields[
        "person_does_thing"
    ]
    assert person_does_thing_definition
    assert person_does_thing_definition.relation_labels == set(
        [
            "does_thing",
            "person_does_thing",
        ]
    )
    assert person_does_thing_definition.reverse_relation_labels == set(
        [
            "is_done_by",
            "is_done_by_person",
        ]
    )

    assert "does_thing" not in Dude._meta.fields
    assert "person_does_thing" not in Dude._meta.fields
    assert "dude_does_thing" in Dude._meta.fields

    dude_does_thing_definition = Dude._meta.fields.relation_fields["dude_does_thing"]
    assert dude_does_thing_definition
    assert dude_does_thing_definition.relation_labels == set(
        ["does_thing", "person_does_thing", "dude_does_thing"]
    )
    assert dude_does_thing_definition.reverse_relation_labels == set(
        ["is_done_by", "is_done_by_person", "is_done_by_dude"]
    )

    # Check this propogates to models by checking Create model
    assert "does_thing" in Agent.Create.model_fields
    assert "does_thing" not in Person.Create.model_fields
    assert "person_does_thing" in Person.Create.model_fields

    assert "does_thing" not in Dude.Create.model_fields
    assert "person_does_thing" not in Dude.Create.model_fields
    assert "dude_does_thing" in Dude.Create.model_fields

    # assert Dude.Create.model_fields["dude_does_thing"].validation_alias == ""
    Dude(label="Dude", doesThing=[{"type": "Task", "id": gen_ulid()}])
    Dude(label="Dude", person_does_thing=[{"type": "Task", "id": gen_ulid()}])


def test_override_relation_raises_error_when_overridden_not_in_parent():
    class Task(BaseNode):
        pass

    class Agent(BaseNode):
        does_thing: Annotated[Task, RelationConfig(reverse_name="is_done_by")]

    class Person(Agent):
        person_does_thing: Annotated[
            Task,
            RelationConfig(
                reverse_name="is_done_by_person", subclasses_relation=["not_there"]
            ),
        ]

    with pytest.raises(PanglossConfigError):
        initialise_models()


def test_override_relation_raises_error_when_overridden_not_subclass_of_parent():
    class Task(BaseNode):
        pass

    class Job(BaseNode):
        pass

    class Endeavour(BaseNode):
        pass

    class SubEndeavour(Endeavour):
        pass

    class BeingLazy(BaseNode):
        pass

    class Agent(BaseNode):
        does_thing: Annotated[
            Task | Job | Endeavour, RelationConfig(reverse_name="is_done_by")
        ]

    class Person(Agent):
        person_does_thing: Annotated[
            SubEndeavour | Job | BeingLazy,  # <-- BeingLazy is not a subclass
            RelationConfig(
                reverse_name="is_done_by_person",
                subclasses_relation=["does_thing"],
            ),
        ]

    with pytest.raises(PanglossConfigError):
        initialise_models()
