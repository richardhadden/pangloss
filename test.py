from pydantic import BaseModel


class Thing(BaseModel):
    name: str | None = None


Thing()

print(Thing())
