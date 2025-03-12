from typing import Literal

from pydantic import BaseModel


class Person(BaseModel):
    type: Literal["Person"] = "Person"
    name: str


p = Person.model_validate({"type": "Person", "name": "John"})

print(p)
print(type(p))
