from pydantic import BaseModel, create_model


class Thing(BaseModel):
    name: str
    
SubThing = create_model("SubThing", __base__=create_model("inter", __base__=Thing, age=(int, ...)), )


SubThing()SubThing()