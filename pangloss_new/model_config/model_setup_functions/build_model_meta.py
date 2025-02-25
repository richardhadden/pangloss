import inspect

from pangloss_new.exceptions import PanglossConfigError
from pangloss_new.model_config.field_definitions import PropertyFieldDefinition
from pangloss_new.model_config.models_base import BaseMeta, RootNode


def initialise_model_meta_inheritance(model: type[RootNode]):
    # Check cls.Meta is a subclass of BaseMeta
    if hasattr(model, "Meta") and not issubclass(model.Meta, BaseMeta):
        raise PanglossConfigError(
            f"Model <{model.__name__}> has a Meta object not inherited from BaseMeta"
        )

    # Check BaseMeta is not used with some name other than cls.Meta
    for class_var_name in vars(model):
        if (
            getattr(model, class_var_name, None)
            and inspect.isclass(getattr(model, class_var_name))
            and issubclass(getattr(model, class_var_name), BaseMeta)
            and class_var_name != "Meta"
        ):
            raise PanglossConfigError(
                f"Error with model <{model.__name__}>: BaseMeta must be inherited from by a class called Meta"
            )

    # Check BaseMeta is not used with some name other than cls.Meta, this time in the class dict
    for field_name in model.__dict__:
        if (
            getattr(model, field_name, None)
            and inspect.isclass(getattr(model, field_name))
            and issubclass(getattr(model, field_name), BaseMeta)
            and field_name != "Meta"
        ):
            raise PanglossConfigError(
                f"Error with model <{model.__name__}>: BaseMeta must be inherited from by a class called Meta"
            )

    parent_class = [
        c for c in model.mro() if issubclass(c, RootNode) and c is not model
    ][0]
    parent_meta = parent_class.Meta

    if "Meta" not in model.__dict__:
        meta_settings = {}
        for field_name in BaseMeta.__dataclass_fields__:
            if field_name == "base_model":
                continue
            meta_settings[field_name] = getattr(parent_meta, field_name)
        meta_settings["abstract"] = False

        model._meta = model.Meta(base_model=model, **meta_settings)

    else:
        meta_settings = {}
        for field_name in BaseMeta.__dataclass_fields__:
            if field_name == "base_model":
                continue
            if field_name == "abstract":
                continue

            if field_name in model.Meta.__dict__:
                meta_settings[field_name] = model.Meta.__dict__[field_name]
            elif field_name in parent_meta.__dict__:
                meta_settings[field_name] = parent_meta.__dict__[field_name]
        if (
            "abstract" in model.Meta.__dict__
            and model.Meta.__dict__["abstract"] is True
        ):
            meta_settings["abstract"] = True

        model._meta = model.Meta(base_model=model, **meta_settings)

        if (
            model.Meta.label_field
            and model.Meta.label_field not in model.__pg_field_definitions__
        ):
            raise PanglossConfigError(
                f"{model.__name__}: trying to use field "
                f"'{model.Meta.label_field}' for label but it is not"
                "a field on the model"
            )
        if model.Meta.label_field and not isinstance(
            model.__pg_field_definitions__[model.Meta.label_field],
            PropertyFieldDefinition,
        ):
            raise PanglossConfigError(
                f"{model.__name__}: trying to use field "
                f"'{model.Meta.label_field}' for label but it is not"
                "a PropertyField"
            )
