from typing import Literal

from ulid import ULID


class FilterableType:
    def __class_getitem__(cls, args):
        print(args[0])
        print(cls)
        return type(f"{cls.__name__}__with__", (cls,), {})


class Person(FilterableType):
    type: Literal["Person"] = "Person"
    name: str
    id: ULID


class Filter:
    def __init__(self, *args, **kwargs):
        self.accumulated_filters = list()

    def __or__(self, other: "Filter"):
        self.accumulated_filters.append(other)
        print(self.accumulated_filters)
        return self.accumulated_filters


p = Person[(Filter(has_type__label="Artist") | Filter(has_type__label="Writer"))]
print(p)
