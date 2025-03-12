from typing import Literal

from pydantic import BaseModel
from ulid import ULID


class Person(BaseModel):
    type: Literal["Person"] = "Person"
    name: str
    id: ULID


p = Person.model_validate(
    {"type": "Person", "name": "John", "id": "01JP537KYYEJCXMARMH7CHPFEC"}
)

print(p)
print(type(p))

print(p.id)
