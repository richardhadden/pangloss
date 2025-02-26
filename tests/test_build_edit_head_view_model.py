from typing import Annotated

from pangloss_new import initialise_models
from pangloss_new.model_config.models_base import EditHeadViewBase
from pangloss_new.models import BaseNode, RelationConfig


def test_build_edit_head_view_model():
    class Statement(BaseNode):
        has_substatement: Annotated[
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
