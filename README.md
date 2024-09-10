# Pangloss
## Prosopography and Network Graph-Labyrinth Orientation System 🔆

## NOTE: this is a rewrite of the core functionality of Pangloss; it is not currently working. Documentation below is to illustrate API


### Premise

_Pangloss_ intends to provide a JSON-based REST API (and, separately, a decoupled JavaScript-based frontend) for modelling data in graph relationships.

The fundamental insight is drawn from the Factoid approach to Prosopography, in which many nodes and edges (between Statement types and Entities) are wrapped in a single Factoid. As such, the Factoid is an _entity_ in a database (thus a node), but also a _subgraph_.

_Pangloss_ aims to generalise this model. While, at the database level, there are only nodes and edges, the models themselves distinguish various kinds of behaviour for the API and interface.



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

#### Limitations:
- fields can only have a single type (no union types)

#### Validation:
The preferred method for validation is via the [`annotated_types` library](https://github.com/annotated-types/annotated-types) and `typing.Annotated`, e.g.

```python
from typing import Annotated
from annotated_types import Gt, Lt

class Adult(Base):
    age: Annotated[int, Gt(18), Lt(120)]

```

## Embedded Nodes

Nodes can be embedded within other nodes attached to a named key. These are stored in the database as separate nodes, but are treated by Pangloss as if they are fully contained within the parent node (e.g. they do not require a `label` field; reverse relations from an Embedded node will point to the parent; they are deleted automatically along with the parent node).

These can be used to group together sets of fields of different types, by using Union of types.


```python
from pangloss import BaseNode, Embedded

class Stuff(BaseNode):
    some_value: str

class OtherStuff(BaseNode):
    some_other_value: str

class Thing(BaseNode):
    embedded_stuff: Embedded[Stuff | OtherStuff]
```

### Relations

Relations are defined on the _source_ node model, and point to a target node model. Relation definitions comprise two parts, the _type_ to be pointed at, and an annotation comprising a `RelationConfig` instance.

```python
from typing import Annotated

from pangloss import BaseNode, RelationConfig

class RelatedThing(BaseNode):
    pass

class ParticularRelatedThing(RelatedThing):
    pass

class Thing(BaseNode):
    related_to: Annotated[RelatedThing, RelationConfig(reverse_name="is_related_thing_of")]
```

#### Relation behaviours

- Relations to a particular type also allow relations to all subclasses of this type (in the example above, `Thing.related_to` allows both `RelatedThing` and its subclass, `ParticularRelatedThing`)

#### The `RelationConfig` object

All relations require annotation with a `RelationConfig` model, which at a minimum provides a `reverse_name` value.



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