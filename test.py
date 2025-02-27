from typing import TypedDict

from pydantic import BaseModel


class kwargs(TypedDict):
    name: str


class Thong(BaseModel):
    age: int
    name: str

    def __init__(self, age: list, **data):
        super().__init__(age=1, **data)


t = Thong(age=[], name="john")
