from pydantic import BaseModel, RootModel, create_model
from pydantic.fields import FieldInfo


class Thing(BaseModel):
    name: str | None = None


class Thong(BaseModel):
    age: int


class Edge(BaseModel):
    value: int


Root = RootModel[Thing | Thong]

A = create_model("asdf", __base__=Root)
A.model_fields["edge"] = FieldInfo(annotation=Edge)
A.model_rebuild()

print(A.model_fields)


a = A(name="john", edge={"value": 1})
a.edge
