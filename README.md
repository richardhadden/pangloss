# Pangloss
## Prosopography and Network Graph-Labyrinth Orientation System 🔆

### Basic modelling

Models are defined by subclassing `BaseNode`, using native Python types.

```python
import datetime

from pangloss import BaseNode

class Thing(BaseNode):
    name: str
    age: int
    features: list[str]
    date_of_birth: datetime.datetime
```

Limitations:
- fields can only have a single type (no union types)



### To note so far


#### Reified Relations

##### CHECK: is this still a requirement with Pydantic 2.9?

"Automatic" reifications can use the Python 3.12 typevar syntax:

```python
class Identification[T](ReifiedRelation[T]):
    pass
```

However, due to some Pydantic requirement, if you wish to *override* the `target` annotation *with a generic*, the generic value must be created as a a `typing.TypeVar`.

```python
T = typing.TypeVar("T")

class Identification(ReifiedRelation[T]):
    target: typing.Annotated[
        T,
        RelationConfig(
            "is_target_of_identification",
            relation_model=IdentificationCertainty,
            validators=[annotated_types.MinLen(1)],
        ),
    ]
```