from pydantic import BaseModel

import typing


class BaseMeta(BaseModel):
    abstract: bool = False
    create: bool = True
    edit: bool = True
    delete: bool = True


class Thing(BaseModel):
    Meta: typing.ClassVar[type[BaseMeta]] = BaseMeta


class SubThing(Thing):
    class Meta(BaseMeta):
        abstract = 1
