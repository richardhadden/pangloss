import datetime
from typing import Annotated, no_type_check

from pangloss_new import initialise_models
from pangloss_new.model_config.models_base import (
    EdgeModel,
    EditHeadViewBase,
    ReifiedRelation,
)
from pangloss_new.models import BaseNode, RelationConfig
from pangloss_new.utils import gen_ulid


@no_type_check
def test_build_edit_head_view_model():
    class Person(BaseNode):
        pass

    class Statement(BaseNode):
        involves_person: Annotated[
            Person,
            RelationConfig(reverse_name="is_involved_in"),
        ]
        has_substatements: Annotated[
            "Statement",
            RelationConfig(
                reverse_name="is_substatement_of", create_inline=True, edit_inline=True
            ),
        ]

    class Factoid(BaseNode):
        has_statements: Annotated[
            Statement,
            RelationConfig(
                reverse_name="is_statement_in", create_inline=True, edit_inline=True
            ),
        ]

    initialise_models()

    assert Factoid.EditHeadView

    assert issubclass(Factoid.EditHeadView, EditHeadViewBase)

    # Test inherit all basic keys from EditHeadViewBase
    for key in [
        "type",
        "id",
        "label",
        "urls",
        "created_by",
        "created_when",
        "modified_by",
        "modified_when",
    ]:
        assert key in Factoid.EditHeadView.model_fields.keys()

    assert "has_statements" in Factoid.EditHeadView.model_fields.keys()

    assert (
        Factoid.EditHeadView.model_fields["has_statements"].annotation
        == list[Statement.View]
    )

    f = Factoid.EditHeadView(
        type="Factoid",
        id=gen_ulid(),
        label="A Factoid",
        urls=[],
        created_by="Smith",
        created_when=datetime.datetime.now(),
        modified_by="Smith",
        modified_when=datetime.datetime.now(),
        has_statements=[
            {
                "type": "Statement",
                "id": gen_ulid(),
                "head_node": gen_ulid(),
                "label": "A statement",
                "involves_person": [
                    {
                        "type": "Person",
                        "id": gen_ulid(),
                        "label": "A Person",
                    }
                ],
                "has_substatements": [],
            }
        ],
    )

    assert f.type == "Factoid"
    assert f.id is not None
    assert f.label == "A Factoid"
    assert f.urls == []
    assert f.created_by == "Smith"
    assert f.modified_by == "Smith"
    assert f.has_statements[0].type == "Statement"
    assert f.has_statements[0].id is not None
    assert f.has_statements[0].label == "A statement"
    assert f.has_statements[0].has_substatements == []

    assert isinstance(f.has_statements[0], Statement.View)
    assert isinstance(f.has_statements[0].involves_person[0], Person.ReferenceView)


@no_type_check
def test_edit_head_view_with_relation_to_reified():
    class Certainty(EdgeModel):
        certainty: int

    class Identification[T](ReifiedRelation[T]):
        target: Annotated[
            T, RelationConfig(reverse_name="is_target_of", edge_model=Certainty)
        ]

    class Person(BaseNode):
        pass

    class Event(BaseNode):
        involves_person: Annotated[
            Person | Identification[Person],
            RelationConfig(reverse_name="is_involved_in"),
        ]

    initialise_models()

    e = Event.EditHeadView(
        type="Event",
        id=gen_ulid(),
        label="An Event",
        urls=[],
        created_by="Smith",
        created_when=datetime.datetime.now(),
        modified_by="Smith",
        modified_when=datetime.datetime.now(),
        involves_person=[
            {
                "type": "Person",
                "id": gen_ulid(),
                "label": "A Person",
            },
            {
                "type": "Identification",
                "id": gen_ulid(),
                "target": [
                    {
                        "type": "Person",
                        "id": gen_ulid(),
                        "label": "A Second Person",
                        "edge_properties": {"certainty": 1},
                    }
                ],
            },
        ],
    )

    assert e.type == "Event"
    assert e.id is not None
    assert e.label == "An Event"
    assert e.urls == []
    assert e.created_by == "Smith"
    assert e.modified_by == "Smith"
    assert e.involves_person[0].type == "Person"
    assert e.involves_person[0].id is not None
    assert e.involves_person[0].label == "A Person"
    assert e.involves_person[1].type == "Identification"
    assert e.involves_person[1].id is not None
    assert e.involves_person[1].target[0].type == "Person"
    assert e.involves_person[1].target[0].id is not None
    assert e.involves_person[1].target[0].label == "A Second Person"
    assert e.involves_person[1].target[0].edge_properties.certainty == 1
    assert isinstance(e.involves_person[0], Person.ReferenceView)
    assert isinstance(e.involves_person[1], Identification[Person].View)
