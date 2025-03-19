# Pangloss
## Prosopography and Network Graph-Labyrinth Orientation System 🔆

## NOTE: this is a rewrite of the core functionality of Pangloss; it is not currently working. Documentation below is to illustrate API


## Premise

_Pangloss_ intends to provide a JSON-based REST API (and, separately, a decoupled JavaScript-based frontend) for modelling data in graph relationships.

It is intended to allow a Factoid approach to Prosopography, in which many nodes and edges (between Statement types and Entities) are wrapped in a single Factoid. As such, the Factoid is an _entity_ in a database (thus a node), but also a _subgraph_ (a tree containing nested statements and references to entities).

_Pangloss_ aims to generalise this model. While, at the database level, there are only nodes and edges, the models themselves distinguish various kinds of behaviour for the API and interface.

## Implementation

_Pangloss_ provides Python-based modelling, using Pydantic classes, coupled with an API using FastAPI.

It provides a database layer (using Python to write Cypher queries) for the database, neo4j. 

(There is no reason for neo4j not to be swapped for something else at some stage: the data modelling, validation and API use _Pangloss_'s own model)

### Basic modelling

Models are defined by subclassing `BaseNode`. Value fields using native Python types.

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
- fields can _only_ have a single type (no union types)

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


## Relations

Relations are _directional_. They are defined on the _source_ node model, and point to a target node model. Relation definitions comprise two parts, the _type_ to be pointed at, and an annotation comprising a `RelationConfig` instance.

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

Reified relations introduce an additional "node" between the subject and object, allowing complex data (including additional relations) to be added.

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
__note__: This isn't the case any more

# Changes from version 0.2

This repo contains the third modelling/database layer rewrite of Pangloss. It uses plain Python classes for model definitions, and builds a more abstract model representation (much more useful for creating frontend types and validators than the previous version, which involved introspecting Pydantic models). Changes are:

- `id`'s are called `id` not `uuid`, and use ULIDs not UUID
- All models have a `_meta` attribute containing abstract model representation
- Multiple inheritance from `BaseNode` types
- Subclassing relations must be a subtype of the subclassed relations
- Can use the superclass name for a field instead of the subclassed one (might be useful)
- `type` field of ReifiedRelation with generic is the generic type, not the non-generic, i.e. `Identification` not `Identification[Person]`
- View/EditView models are distinguished from `HeadView`/`HeadEditView` models — the `Head` variety is for the top node (i.e. the one requested by the API), others for contained nodes
- All contained nodes carry a reference to the `HeadNode` (better for indexing, and direct lookup of context)
- Some really sneaky methods for allowing lookups of specialised models (e.g. with relation via `EdgeModel`): `Person.View.via.Certainty`
- Authentication is using AuthX, not the FastAPI homespun example
- When allowed via `Meta` configuration, a new instance of a model can be created via a reference (really only useful for 'empty' — i.e. only a label — models), with a user-provided ULID or external URI or list of URIs (in latter case, _Pangloss_ generates a new ULID and stores the URI)
- `id` for search can also take a URI
- URIs are stored in separate nodes (and can be edited)
- Periodic background tasks can be registered using `@background_task` decorator
- Subclassed relation types also create supertype of the relation (e.g. if `Person.is_friends_with` is a subtype of `Person.knows`, creating the former will also create an edge for the latter); these additional edges are marked with `_pg_shortcut": True,` as a property.
- Deferred database writes: writing additional shortcut edges is slow, and is only useful for later querying; therefore, the primary write/update queries can be run and result returned to the user, and the inferred shortcuts written afterwards as a background task

# TODO:
- DB layer


# Full model example for Factoid model using most features

```python
class Certainty(EdgeModel):
    certainty: float

class Identification[T](ReifiedRelation[T]):
    target: Annotated[
        T, RelationConfig(reverse_name="is_target_of", edge_model=Certainty)
    ]

class WithProxy[T](ReifiedRelationNode):
    proxy: Annotated[
        T,
        RelationConfig(reverse_name="acts_as_proxy_in"),
    ]

class Reference(BaseNode):
    pass

class Citation(BaseNode):
    source: Annotated[
        Reference,
        RelationConfig(reverse_name="is_source_of"),
    ]
    page: int

class Factoid(BaseNode):
    Embedded[Citation]
    has_statements: Annotated[
        Statement,
        RelationConfig(
            reverse_name="is_statement_in", create_inline=True, edit_inline=True
        ),
    ]

class Entity(BaseNode):
    class Meta(BaseMeta):
        abstract = True
        create_by_reference = True

class Person(Entity):
    pass

class Object(Entity):
    pass

class Statement(BaseNode):
    class Meta(BaseMeta):
        abstract = True

class Order(Statement):
    person_giving_order: Annotated[
        WithProxy[Identification[Person]],
        RelationConfig(reverse_name="gave_order"),
    ]
    person_receiving_order: Annotated[
        Identification[Person],
        RelationConfig(
            reverse_name="received_order",
        ),
    ]
    thing_ordered: Annotated[
        CreationOfObject,
        RelationConfig(
            reverse_name="was_ordered_in",
            bind_fields_to_related=[
                BoundField(
                    parent_field_name="person_receiving_order",
                    bound_field_name="person_creating_object",
                )
            ],
        ),
    ]

class CreationOfObject(Statement):
    person_creating_object: Annotated[
        WithProxy[Identification[Person]],
        RelationConfig(reverse_name="creator_in_object_creation"),
    ]
    object_created: Annotated[Object, RelationConfig(reverse_name="was_created_in")]

```