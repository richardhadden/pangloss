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

class Adult(BaseNode):
    age: Annotated[int, Gt(18), Lt(120)]

```

#### Multi-Key Fields

It is possible to create dictionary-like objects as values for a field using `MultiKeyField`. This takes
a generic type, which is applied to the key `value`, and any other number of literal fields.

```python
from pangloss import BaseNode, MultiKeyField

class WithCertainty[T](MultiKeyField[T]):
    certainty: int

class Person(BaseNode):
    name: WithCertainty[str]

p = Person(label="J Smith", name={"value": "John Smith", "certainty": 1})
```

At the database level, these fields are flattened into quadruple-underscore-separated 
keys, i.e. `name____value`, `name____certainty`.

A `MultiKeyField` can only take literal types (`str`, `int`, etc.) or `list[]`, not relations to nodes
or deeper-nested dictionaries.


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

n.b. **Embedded nodes cannot currently have relation fields through Reified Relations.**

## Relations

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
- Relations can also declared to `typing.Union` types, e.g.:

```python

class Cat(BaseNode):
    pass

class Dog(BaseNode):
    pass

class Person(BaseNode):
    has_pet: Annotated[
        Cat | Dog, 
        RelationConfig(reverse_name="is_pet_of")
    ]
```

#### The `RelationConfig` object

All relations require annotation with a `RelationConfig` model, which at a minimum provides a `reverse_name` value.

#### `EdgePropertiesModel`

Properties can also be added to the Edge (relation) between two nodes. These should be defined by subclassing `EdgeProperties`:

```python
from typing import Annotated
from pangloss import BaseNode, EdgeProperties, RelationConfig

class EdgeWithAdditionalNotes(EdgeProperties):
    notes: str

class RelatedThing(BaseNode):
    pass

class Thing(BaseNode):
    related_to: Annotated[
        RelatedThing, 
        RelationConfig(
            reverse_name="is_related_thing_of", edge_model=EdgeWithAdditionalNotes
        )
    ]
```

### Traits

Traits (`HeritableTrait` and `NonHeritableTrait`) are mixin-like classes that can be applied to `BaseNode` types. Traits can be the _object_ of a relation, and can be viewed independently. 

```python
from typing import Annotated

from pangloss import BaseNode, HeritableTrait, RelationConfig

class Purchaseable(HeritableTrait):
    cost: int

class Vegetable(BaseNode, Purchaseable):
    pass

class Cow(BaseNode, Purchaseable):
    pass

class SmallCow(Cow):
    pass

class Person(BaseNode):
    owns_thing: Annotated[
        Purchaseable, 
        RelationConfig(reverse_name="has_owner")]
```

In the above example, `Person.owns_thing` can point to all subclasses of `Purchaseable` (i.e. `Vegetable`, `Cow` and `SmallCow` — `SmallCow` inherits its `Purchaseable` trait from `Cow`)

`NonHeritableTrait` functions in the same way as `HeritableTrait`, with exception that it is applied _only_ to the classes to which it is _directly_ applied (not subclasses of those classes). This allows arbitrary cross-cutting of the principal object hierarchy.

### Reified Relations

Reified relations introduce an additional node between the subject and object, allowing complex data (including additional relations) to be added.

```python
from pangloss import BaseNode, RelationConfig, ReifiedRelation

class Person(BaseNode):
    pass

class PersonRepresentsOtherPerson(ReifiedRelation):
    target: Annotated[
        Person, 
        relation_config(reverse_name="is_target_of")]

    representative: Annotated[
        Person, 
        relation_config(reverse_name="acts_as_representative_in")]

class LegalCase(BaseNode):
    plaintiff: Annotated[
        PersonRepresentsOtherPerson, 
        RelationConfig("is_plaintiff_in")]

```

`target` is a required field of a `ReifiedRelation` object. This allows the full relationship (from `LegalCase.plaintiff` to the object, `Person`) to be followed as a single relation.

`ReifiedRelation` can also be defined as a Generic type, which will be automatically be applied as a type of `target`. (The example below uses)

```python
from typing import Annotated
from pangloss import BaseNode, RelationConfig, ReifiedRelation

class Identification[T](ReifiedRelation[T]):
    reason_for_identification: str
    other_possible_person: Annotated[
        Person, 
        RelationConfig(reverse_name="other_possible_person_in")]

class Person(BaseNode):
    pass

class Event(BaseNode):
    participant: Annotated[
        Identification[Person], 
        RelationConfig(reverse_name="participant_in")]
```

__Note__: _Generic_ reified relations cannot take a union type or a Trait type as the type argument.
Use a union of generic reified relations if necessary.

### Viewing/Creating/Editing Inline

_Pangloss_ moves away from the simple graph paradigm of nodes representing entities, connected by typed edges.

While this approach is useful in places (a node represents a Person, for example), it is useful to consider conceptually – and to create data pragmatically — directed subgraphs. 

A Factoid is one such case: as an "entity", a Factoid is a node — but it is (logically) a container for all the statements contained within it.

Pangloss therefore allows the viewing, creating and editing "inline" of nested objects. The "inline" objects are nevertheless standalone nodes and may be viewed as such (this differs from Embedded Nodes — see above — which are fully dependent on the parent node).

A relation to a node type allows the creation of a complete node of that type "inline", rather than being provided as a reference.

Inline viewing/creation/editing therefore serves as the abstract model for the implementation of directed subgraphs that function as "entities" in their own right.


## Generated Classes

_Pangloss_ makes extensive use of auto-generated classes, with the intention of fulfilling CRUD operations via the API.

### To note so far


#### Reified Relations

"Automatic" reifications can use the Python 3.12 typevar syntax:

```python
class Identification[T](ReifiedRelation[T]):
    pass
```

However, due to some Pydantic requirement, if you wish to *override* the `target` annotation *with a generic*, the generic value must be created as a a `typing.TypeVar`.

```python
TIdentificationTarget = typing.TypeVar("TIdentificationTarget")

class Identification(ReifiedRelation[TIdentificationTarget]):
    target: typing.Annotated[
        TIdentificationTarget,
        RelationConfig(
            "is_target_of_identification",
            edge_model=IdentificationCertainty,
            validators=[annotated_types.MinLen(1)],
        ),
    ]
```


# TODO:


- DB layer
- API layer
- Allow reified relations from Embedded nodes
- Allow edge models on Embedded nodes


## Bugs:

- Incoming relation does not allow subclasses
- Embedded .Set is the full Set of the model, not of the Embedded.. so requires UUID, label etc. (maybe need to distinguish between EmbeddedSet and EmbeddedCreate??)