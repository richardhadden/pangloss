from __future__ import annotations

from typing import Annotated
import uuid

from pangloss.models import BaseNode, ReifiedRelation, RelationConfig
from pangloss.model_config.model_manager import ModelManager


class Person(BaseNode):
    pass


class Identification[T](ReifiedRelation[T]):
    pass


class Event(BaseNode):
    carried_out_by: Annotated[
        Identification[Person], RelationConfig(reverse_name="carried_out")
    ]


ModelManager.initialise_models()


event = Event(
    type="Event",
    label="A Nice Event",
    carried_out_by=[
        {
            "type": "Identification[Person]",
            "target": [{"type": "Person", "uuid": uuid.uuid4()}],
        }
    ],
)
