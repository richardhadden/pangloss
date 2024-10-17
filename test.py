from pydantic import BaseModel, ConfigDict


class Thing(BaseModel):
    name: str

    model_config = ConfigDict(extra="allow")


t = Thing(name="John", some_other_thing="a value")

print(t)  #
