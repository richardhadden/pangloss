import datetime
from typing import Annotated, no_type_check

from pangloss_new import initialise_models
from pangloss_new.model_config.models_base import (
    EdgeModel,
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
