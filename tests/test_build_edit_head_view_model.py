import datetime
from typing import Annotated, no_type_check

from pangloss_new import initialise_models
from pangloss_new.model_config.models_base import EditHeadViewBase
from pangloss_new.models import BaseNode, RelationConfig
from pangloss_new.utils import gen_ulid


@no_type_check
def test_build_edit_head_view_model():
    class Statement(BaseNode):
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
