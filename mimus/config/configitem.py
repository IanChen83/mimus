from types import SimpleNamespace
from copy import copy

from .error import ConfigError

__all__ = ("ConfigItem",)


class ConfigItem(SimpleNamespace):
    """A class that is inteded to be inherited to subclass
    `types.SimpleNamespace` and provides value trasformation and
    validation.
    """

    __slots__ = ()

    def __init__(self, **kwargs):
        new_kwargs = {}
        for field in self._fields:
            if field in kwargs:
                new_kwargs[field] = kwargs.pop(field)
            elif field in self._defaults:
                new_kwargs[field] = copy(self._defaults.get(field))
            else:
                raise ConfigError(f"'{field}' is a required field")

        if kwargs:
            names = ", ".join(kwargs)
            raise ConfigError(
                f"{self.__class__.__name__} get unexpected field(s) '{names}'"
            )

        # Call SimpleNamespace.__init__ to set field values.
        super().__init__(**new_kwargs)

        for field in self._fields:
            value = getattr(self, field)

            # transform value
            if hasattr(self, f"_transform_{field}"):
                value = getattr(self, f"_transform_{field}")(value)
                setattr(self, field, value)

            # validate value
            if hasattr(self, f"_validate_{field}"):
                getattr(self, f"_validate_{field}")(value)

    def __init_subclass__(cls, fields="", defaults=None, **kwargs):
        super().__init_subclass__(**kwargs)

        # normalize parameters
        if isinstance(fields, str):
            fields = fields.replace(",", " ").split()
        fields = tuple(map(str, fields))

        defaults = defaults or {}

        # ensure all keys in defaults can be found in fields
        for key in defaults:
            if key not in fields:
                raise TypeError(f"Key '{key}' in default dict not found in field names")

        cls._fields = fields
        cls._defaults = defaults

    def copy(self):
        new_obj = self.__class__.__new__(self.__class__)
        for field in self._fields:
            setattr(new_obj, field, getattr(self, field))
        return new_obj

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

    def to_dict(self):
        return {field: getattr(self, field) for field in self._fields}

    def __eq__(self, value):
        if self.__class__ != value.__class__:
            return False

        return super().__eq__(value)

    def __repr__(self):
        arg_list = ", ".join(f"{k}={getattr(self, k)!r}" for k in self._fields)
        return f"{type(self).__name__}({arg_list})"
