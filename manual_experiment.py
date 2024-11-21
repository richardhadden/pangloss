from pydantic import BaseModel

import typing


class BaseConfig(BaseModel):
    name: str


class Thing(BaseModel):
    Settings: typing.ClassVar[type[BaseConfig]]


class SubThing(Thing):
    pass
