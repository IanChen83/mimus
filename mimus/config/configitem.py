from types import SimpleNamespace
from copy import copy
from functools import wraps

from .error import ConfigError

__all__ = ("ConfigItem",)


class ConfigItem(SimpleNamespace):
    """A class that is inteded to be inherited to subclass
    `types.SimpleNamespace` and provides value trasformation and
    validation.
    """

    __slots__ = ()

    def __init_subclass__(cls, fields="", defaults=None, **kwargs):
        super().__init_subclass__(**kwargs)

        # normalize parameters
        if isinstance(fields, str):
            fields = fields.replace(",", " ").split()
        fields = list(map(str, fields))

        defaults = defaults or {}

        # ensure all keys in defaults can be found in fields
        for key in defaults:
            if key not in fields:
                raise TypeError(f"Key '{key}' in default dict not found in field names")

        cls._fields = fields
        cls._defaults = defaults

        setattr(
            cls,
            "__init__",
            _get_init_wrapper(getattr(cls, "__init__"), fields, defaults),
        )

    def to_dict(self):
        return {field: getattr(self, field) for field in self._fields}

    def __eq__(self, value):
        if self.__class__ != value.__class__:
            return False

        return self.to_dict() == value.to_dict()

    def __hash__(self):
        # A config item is hashable if and only if all of its field values are hashable.
        return hash(tuple(getattr(self, field) for field in self._fields))

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


def _get_init_wrapper(fn, fields, defaults):
    @wraps(fn)
    def __init__(self, **kwargs):
        new_kwargs = {}
        for field in fields:
            if field in kwargs:
                new_kwargs[field] = kwargs.pop(field)
            elif field in defaults:
                new_kwargs[field] = copy(defaults.get(field))
            else:
                raise ConfigError(f"'{field}' is a required field")

        if kwargs:
            names = ", ".join(kwargs)
            raise ConfigError(
                f"{self.__class__.__name__} get unexpected field(s) '{names}'"
            )

        fn(self, **new_kwargs)

        # From here onwards, we use getattr() to get instance attribute
        # because the init function of the subclass might modify its
        # field values.
        for field in fields:
            value = getattr(self, field)

            # transform value
            if hasattr(self, f"_transform_{field}"):
                value = getattr(self, f"_transform_{field}")(value)
                setattr(self, field, value)

            # validate value
            if hasattr(self, f"_validate_{field}"):
                getattr(self, f"_validate_{field}")(value)

    return __init__
