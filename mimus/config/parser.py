"""
parser parses config files
"""
from pathlib import Path
from itertools import chain

from ruamel.yaml import YAML


__all__ = (
    "CURRENT_VERSION",
    "SUPPORTED_PARSERS",
    "load",
    "loads",
    "Config",
    "Parser",
    "StackServiceItem",
    "TemplateServiceItem",
    "ServiceItem",
    "ConfigError",
)


CURRENT_VERSION = 0
SUPPORTED_PARSERS = (0,)


def _get_repr_function(keys, optional_keys=tuple()):
    def fn(self):
        items = list("{}={!r}".format(k, self.__dict__[k]) for k in keys)
        for key in optional_keys:
            if self.__dict__[key]:
                items.append("{}={!r}".format(key, self.__dict__[key]))

        return "{}({})".format(type(self).__name__, ", ".join(items))

    return fn


def load(f, *, file=""):
    """
    load loads configurations from file reader.
    """
    return loads(f.read(), file=file)


def loads(data, *, file=""):
    """
    loads loads configurations from string.
    """
    if file == "":
        cwd = Path(file)
    else:
        file_path = Path(file)
        if not file_path.is_file():
            raise ConfigError("'file' should be a valid file path")
        cwd = file_path.parent

    parser = Parser.parse(data, cwd, file)


class Parser:
    def __init__(self):
        self.root = None
        self.services = {}
        self.includes = {}
        self.configs = {}

    def parse_config(self, content, cwd, file):
        cwd = cwd.resolve()
        if file != "":
            file = str(Path(file).resolve())

        if file not in self.configs:
            self.configs[file] = _parse_config_by_version(content, cwd, file=file)

        return self.configs[file]

    def register_include(self, inc):
        if inc.name not in self.includes:
            self.includes[inc.name] = inc
            return

        prev = self.includes[inc.name]
        if prev.path.samefile(inc.path):
            return

        if inc.file and prev.file:
            err_msg = (
                "Duplicate include name '{}' but differnt config path"
                "{} and {} found in {} and {}."
            ).format(inc.name, inc.path, prev.path, inc.file, prev.file)
        else:
            err_msg = (
                "Duplicate include name '{}' but differnt config path"
                "{} and {} found."
            ).format(inc.name, inc.path, prev.path)

        raise ConfigError(err_msg)

    def register_service(self, service):
        if service.name in self.services:
            prev = self.services[service.name]
            if service.file and prev.file:
                err_msg = "Duplicate service name '{}' found in {} and {}".format(
                    service.name, service.file, prev.file
                )
            else:
                err_msg = "Duplicate service name '{}' found".format(service.name)

            raise ConfigError(err_msg)

        self.services[service.name] = service

    @classmethod
    def parse(cls, content, cwd, file=""):
        parser = cls()

        config = parser.parse_config(content, cwd, file)
        parser.root = config

        unhandled_includes = list(config.includes)
        while unhandled_includes:
            inc = unhandled_includes.pop(0)

            parser.register_include(inc)
            if str(inc.path) not in parser.configs:
                # If inc.path is already in the config list, we won't
                # parse it (and append includes) again. This allows users
                # to include the same file multiple times with different names.
                with inc.path.open() as f:
                    content = f.read()

                config = parser.parse_config(content, inc.path.parent, str(inc.path))
                unhandled_includes.extend(config.includes)

        for service in chain.from_iterable(
            config.services for config in parser.configs.values()
        ):
            if not hasattr(service, "name"):
                continue
            parser.register_service(service)

        return parser

    def iter_service(self):
        if self.root is None:
            return

        unhandled_services = list(reversed(self.root.services))

        included_stacks = set()
        while unhandled_services:
            service = unhandled_services.pop()
            if isinstance(service, StackServiceItem):
                if service.stack in included_stacks:
                    continue

                unhandled_services.extend(reversed(self.resolve_stack(service)))
                included_stacks.add(service.stack)

            elif isinstance(service, TemplateServiceItem):
                unhandled_services.append(self.resolve_template(service))

            elif isinstance(service, ServiceItem):
                yield service

            else:
                raise RuntimeError(
                    "Unexpected ServiceItemType '{}'".format(service.item_type)
                )

    def resolve_template(self, obj):
        if obj.template not in self.services:
            raise ConfigError(
                "Cannot find template '{}' for service '{}'".format(
                    obj.template, obj.name,
                ),
                file=obj.file,
            )
        template = self.services[obj.template]
        new_obj = template.copy()
        new_obj.name = obj.name
        new_obj.set_attrs_from(obj)

        new_obj.file = obj.file
        new_obj.inherits = ("template:" + template.name, *template.inherits)

        return new_obj

    def resolve_stack(self, obj):
        if obj.stack not in self.includes:
            raise ConfigError(
                "Cannot find stack with name '{}'".format(obj.stack), file=obj.file,
            )

        stack_path = self.includes[obj.stack].path
        config = self.configs[str(stack_path)]
        results = config.services.copy()

        for service in results:
            service.inherits = ("stack:" + obj.stack, *service.inherits)

        return results


class Config:
    def __init__(self, obj, cwd, *, file=""):
        self.file = file

        self.cwd = cwd
        items = obj.get("includes", [])
        services = obj.get("services", [])

        self.includes = [self._parse_include(item) for item in items]
        self.services = [self._parse_service(item) for item in services]

    def _parse_include(self, item):
        if "name" not in item:
            raise ConfigError(
                "includes.item should have attribute 'name'", file=self.file
            )

        if "path" not in item:
            raise ConfigError(
                "includes.item should have attribute 'path'", file=self.file
            )

        name = item.get("name")
        path = self.cwd.joinpath(item.get("path"))

        return IncludeItem(name, path, file=self.file)

    def _parse_service(self, item):
        service_types = (
            StackServiceItem,
            TemplateServiceItem,
            ServiceItem,
        )

        for _type in service_types:
            if _type.match(item):
                return _type(item, file=self.file)

        definitions = " or ".join(
            "[{}]".format(_type.match_definition) for _type in service_types
        )
        raise ConfigError(
            "Service {} doesn't match any service definition {}".format(
                item, definitions
            ),
            file=self.file,
        )


class IncludeItem:
    def __init__(self, name, path, *, file=""):
        self.file = file

        if name == "":
            raise ConfigError("includes.item.name cannot be an empty string", file=file)

        if not path.is_file():
            raise ConfigError(
                (
                    "includes.item '{}' with path {} " "should point to a config file"
                ).format(name, path),
                file=file,
            )

        self.name = name
        self.path = path.resolve()

    __repr__ = _get_repr_function(("name", "path"), ("file",))

    def __eq__(self, value):
        return self.name == value.name and self.path.samefile(value.path)


class StackServiceItem:

    match_type = "stack"

    match_definition = "Item contains 'stack' field"

    def __init__(self, item: dict, *, file="", inherits=tuple()):
        item = item.copy()
        stack = item.pop("stack")
        if stack == "":
            raise ConfigError(
                "If specified, services.item.stack cannot be an empty string", file=file
            )

        if item:
            raise ConfigError(
                "Unexpected field(s) when specifying stack '{}': {}".format(
                    stack, ", ".join(item)
                ),
                file=file,
            )

        self.stack = stack

        self.file = file
        self.inherits = inherits

    __repr__ = _get_repr_function(("stack",), ("file", "inherits"))

    def __eq__(self, value):
        return self.stack == value.stack

    @classmethod
    def match(cls, item):
        return "stack" in item


class ServiceItem:

    match_type = "service"

    match_definition = "Item contains 'name' field"

    def __init__(self, item: dict, *, file="", inherits=tuple()):
        item = item.copy()
        name = item.pop("name")
        if name == "":
            raise ConfigError(
                "If specified, services.item.name cannot be an empty string", file=file
            )

        self.name = name
        self.host = item.pop("host", "")
        self.path = item.pop("path", "")
        self.port = item.pop("port", 0)
        self.protocol = item.pop("protocol", "")
        self.method = item.pop("method", "")
        self.handler = item.pop("handler", "")
        self.tlskey = item.pop("tlskey", "")
        self.tlscert = item.pop("tlscert", "")

        self.inherits = inherits
        self.file = file

        if item:
            raise ConfigError(
                "Unexpected field(s) when specifying service '{}': {}".format(
                    name, ", ".join(item)
                ),
                file=file,
            )

    __repr__ = _get_repr_function(
        ("name",),
        (
            "host",
            "path",
            "port",
            "protocol",
            "method",
            "handler",
            "tlskey",
            "tlscert",
            "file",
            "inherits",
        ),
    )

    def __eq__(self, value):
        return (
            self.name == value.name
            and self.host == value.host
            and self.path == value.path
            and self.port == value.port
            and self.protocol == value.protocol
            and self.method == value.method
            and self.handler == value.handler
            and self.tlskey == value.tlskey
            and self.tlscert == value.tlscert
        )

    def copy(self):
        new_obj = self.__class__(dict(name=self.name), file=self.file)
        new_obj.host = self.host
        new_obj.path = self.path
        new_obj.port = self.port
        new_obj.protocol = self.protocol
        new_obj.method = self.method
        new_obj.handler = self.handler
        new_obj.tlskey = self.tlskey
        new_obj.tlscert = self.tlscert

        return new_obj

    def set_attrs_from(self, obj):
        if obj.host:
            self.host = obj.host
        if obj.path:
            self.path = obj.path
        if obj.port:
            self.port = obj.port
        if obj.protocol:
            self.protocol = obj.protocol
        if obj.method:
            self.method = obj.method
        if obj.handler:
            self.handler = obj.handler
        if obj.tlskey:
            self.tlskey = obj.tlskey
        if obj.tlscert:
            self.tlscert = obj.tlscert

    @classmethod
    def match(cls, item):
        return "name" in item


class TemplateServiceItem(ServiceItem):

    match_type = "template"

    match_definition = "Item contains 'template' field and Item matches a service"

    def __init__(self, item, *, file="", inherits=tuple()):
        item = item.copy()
        template = item.pop("template")
        if template == "":
            raise ConfigError(
                "If specified, services.item.template cannot be an empty string",
                file=file,
            )

        super().__init__(item, file=file, inherits=inherits)
        self.template = template

    __repr__ = _get_repr_function(
        ("name", "template"),
        (
            "host",
            "path",
            "port",
            "protocol",
            "method",
            "handler",
            "tlskey",
            "tlscert",
            "file",
            "inherits",
        ),
    )

    def __eq__(self, value):
        return self.template == value.template and super().__eq__(value)

    @classmethod
    def match(cls, item):
        return "template" in item and super().match(item)

    def copy(self):
        new_obj = super().copy()
        new_obj.template = self.template
        return new_obj


def _load_obj(data):
    yaml = YAML()
    return yaml.load(data) or {}


def _parse_config_by_version(data, cwd, file=""):
    obj = _load_obj(data)

    version = obj.get("version", CURRENT_VERSION)
    if not isinstance(version, int):
        raise ConfigError("Invalid version {}".format(version), file=file)

    if version == 0:
        config_cls = Config
    else:
        raise ConfigError("Version {} is not supported".format(version), file=file)

    if file != "":
        config = config_cls(obj, cwd, file=file)
    else:
        config = config_cls(obj, cwd)

    return config


class ConfigError(Exception):
    def __init__(self, reason, **meta):
        self.meta = meta

        items = tuple("{}={!r}".format(k, v) for k, v in meta.items() if bool(v))
        if items:
            reason = "{}, ({})".format(reason, ", ".join(items))

        super().__init__(reason)
