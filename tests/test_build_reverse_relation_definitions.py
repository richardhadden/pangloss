from typing import no_type_check

from pangloss_new.models import BaseNode


@no_type_check
def test_build_reverse_relation_definition_simple():
    class Person(BaseNode):
        pass

    class Event(BaseNode):
        # involves_person: Annotated[Person, RelationConfig]
        pass
