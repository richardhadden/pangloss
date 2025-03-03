from typing import Any, Literal, Union

from pydantic import BaseModel, Field, RootModel


class MessageModelV1(BaseModel):
    version: Literal[1]
    bar: str


class MessageModelV2(BaseModel):
    version: Literal[2]
    foo: str


MessageType = Union[MessageModelV1, MessageModelV2]


class OuterMessageModel(RootModel):
    root: MessageType = Field(discriminator="version")


def MessageModel(**kwargs: Any) -> MessageType:
    return OuterMessageModel.model_validate(kwargs).root


obj1 = MessageModel(version=1, bar="a")
obj2 = MessageModel(version=2, foo="b")
