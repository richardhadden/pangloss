from typing import Literal

from pydantic import BaseModel, model_validator


class Person(BaseModel):
    type: Literal["Person"] = "Person"
    name: str


class DidThing(BaseModel):
    type: Literal["DidThing"] = "DidThing"
    carried_out_by: Person


class Order(BaseModel):
    type: Literal["Order"] = "Order"
    carried_out_by: Person
    thing_ordered: list[DidThing]

    @model_validator(mode="before")
    @classmethod
    def thing(cls, data):
        for c in data["thing_ordered"]:
            c["carried_out_by"] = data["carried_out_by"]
        return data


o = Order(
    type="Order",
    carried_out_by=Person(type="Person", name="John"),
    thing_ordered=[
        {
            "type": "DidThing",
            "carried_out_by": {"type": "Person", "name": "Toby"},
        }
    ],
)

print(o)
