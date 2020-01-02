"""
parser parses config files
"""
from pathlib import Path
from itertools import chain

from ruamel.yaml import YAML


__all__ = (
    'CURRENT_VERSION',
    'SUPPORTED_PARSERS',
    'load',
    'loads',
    'Parser',
    'State',
    'StackServiceItem',
    'TemplateServiceItem',
    'ServiceItem',
    'ConfigError',
)


CURRENT_VERSION = 0
SUPPORTED_PARSERS = (0,)


"""
1. construct parser inclusion graph
1. get version from object
2. get parser based on version
3. return services with metadata for debugging

for the current parser
1. parse includes
2. return services
"""


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

    state = State()
    state.parse(data, cwd)


class State:
    def __init__(self):
        self.services = {}
        self.includes = {}
        self.parsers = {}

    def parse(self, content, cwd, file=""):
        cwd = cwd.resolve()
        parser = _create_parser(content, cwd, file=file)
        self.parsers[file] = parser

        self._init(parser)

    def _init(self, parser):
        unhandled_includes = list(parser.includes)

        while unhandled_includes:
            inc = unhandled_includes.pop(0)

            if inc.name in self.includes:
                prev = self.includes[inc.name]
                if prev.path.samefile(inc.path):
                    continue

                raise ConfigError((
                    "Duplicate include name '{}' but differnt config path"
                    "{} and {} found in {} and {}"
                ).format(
                    inc.name, inc.path, prev.path, inc.file, prev.file,
                ))

            if str(inc.path) not in self.parsers:
                # If inc.path is already in the parser list, we won't
                # parse it (and append includes) again. This allows users
                # to include the same file multiple times (as long as the
                # names are different).
                with inc.path.open() as f:
                    content = f.read()
                    cwd = inc.path.parent.resolve()
                    file = str(inc.path)

                    parser = _create_parser(content, cwd, file=file)
                    self.parsers[file] = parser
                    unhandled_includes.extend(parser.includes)

            self.includes[inc.name] = inc

        for _parser in chain.from_iterable(parser for parser in self.parsers):
            service = _parser.services

            if not hasattr(service, "name"):
                continue

            if service.name in self.services:
                prev = self.services[service.name]
                raise ConfigError(
                    "Duplicate service name '{}' found in {} and {}".format(
                        service.name, service.file, prev.file,
                    ))

            self.services[service.name] = service

    def collect_services(self, parser):
        # The local 'service' variable is the returned value containing
        # ordered services, while State.services is a mapping from service
        # names to service definitions.
        services = []
        unhandled_services = list(reversed(parser.services))

        included_stacks = set()
        while unhandled_services:
            service = unhandled_services.pop()
            if isinstance(service, StackServiceItem):
                stack = service.stack
                if stack not in self.includes:
                    raise ConfigError(
                        "Cannot find stack with name '{}'".format(stack),
                        file=service.file)

                inc = self.includes[stack]
                parser = self.parsers[str(inc.path)]
                if parser in included_stacks:
                    continue
                included_stacks.add(parser)

                unhandled_services.extend(
                    reversed(self.resolve_stack(parser)))

            elif isinstance(service, TemplateServiceItem):
                template = service.template
                if template not in self.services:
                    raise ConfigError(
                        "Cannot find template witth name '{}'".format(
                            template),
                        file=service.file)

                services.append(self.resolve_template(
                    self.services[template]))

            elif isinstance(service, ServiceItem):
                services.append(service)

            else:
                raise RuntimeError(
                    "Unexpected ServiceItemType '{}'".format(service.item_type))

        return services

    def resolve_template(self, template):
        pass

    def resolve_stack(self, stack):
        pass


class Parser:
    def __init__(self, obj, cwd, *, file=""):
        self.file = file

        self.cwd = cwd
        items = obj.get("includes", [])
        services = obj.get("services", [])

        self.includes = [self._parse_include(item) for item in items]
        self.services = [self._parse_service(item) for item in services]

    def _parse_include(self, item):
        if 'name' not in item:
            raise ConfigError(
                "includes.item should have attribute 'name'",
                file=self.file)

        if 'path' not in item:
            raise ConfigError(
                "includes.item should have attribute 'path'",
                file=self.file)

        name = item.get('name')
        path = self.cwd.joinpath(item.get('path'))

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

        definitions = " or ".join("[{}]".format(_type.match_definition)
                                  for _type in service_types)
        raise ConfigError(
            "Service {} doesn't match any service definition {}".format(
                item, definitions),
            file=self.file)


class IncludeItem:
    def __init__(self, name, path, *, file=""):
        self.file = file

        if name == "":
            raise ConfigError(
                "includes.item.name cannot be an empty string",
                file=file)

        if not path.is_file():
            raise ConfigError(
                ("includes.item '{}' with path {} "
                 "should point to a config file").format(name, path),
                file=file)

        self.name = name
        self.path = path.resolve()

    __repr__ = _get_repr_function(("name", "path"), ("file", ))

    def __eq__(self, value):
        return self.name == value.name and self.path.samefile(value.path)


class StackServiceItem:

    match_type = "stack"

    match_definition = "Item contains 'stack' field"

    def __init__(self, item: dict, *, file=""):
        item = item.copy()
        stack = item.pop("stack")
        if stack == "":
            raise ConfigError(
                "If specified, services.item.stack cannot be an empty string",
                file=file)

        if item:
            raise ConfigError(
                "Unexpected field(s) when specifying stack '{}': {}".format(
                    stack, ", ".join(item)),
                file=file)

        self.stack = stack
        self.file = file

    __repr__ = _get_repr_function(("stack", ), ("file", ))

    def __eq__(self, value):
        return self.stack == value.stack

    @classmethod
    def match(cls, item):
        return "stack" in item


class ServiceItem:

    match_type = "service"

    match_definition = "Item contains 'name' field"

    def __init__(self, item: dict, *, file=""):
        item = item.copy()
        name = item.pop("name")
        if name == "":
            raise ConfigError(
                "If specified, services.item.name cannot be an empty string",
                file=file)

        self.file = file
        self.name = name
        self.host = item.pop("host", "")
        self.path = item.pop("path", "")
        self.port = item.pop("port", 0)
        self.protocol = item.pop("protocol", "")
        self.method = item.pop("method", "")
        self.handler = item.pop("handler", "")
        self.tlskey = item.pop("tlskey", "")
        self.tlscert = item.pop("tlscert", "")

        if item:
            raise ConfigError(
                "Unexpected field(s) when specifying service '{}': {}".format(
                    name, ", ".join(item)),
                file=file)

    __repr__ = _get_repr_function(
        ("name", ),
        ("host",
         "path",
         "port",
         "protocol",
         "method",
         "handler",
         "tlskey",
         "tlscert",
         "file"),
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

    @classmethod
    def match(cls, item):
        return "name" in item


class TemplateServiceItem(ServiceItem):

    match_type = "template"

    match_definition = "Item contains 'template' field and Item matches a service"

    def __init__(self, item, *, file=""):
        item = item.copy()
        template = item.pop("template")
        if template == "":
            raise ConfigError(
                "If specified, services.item.template cannot be an empty string",
                file=file)

        super().__init__(item, file=file)
        self.template = template

    __repr__ = _get_repr_function(
        ("name", "template"),
        ("host",
         "path",
         "port",
         "protocol",
         "method",
         "handler",
         "tlskey",
         "tlscert",
         "file"))

    def __eq__(self, value):
        return self.template == value.template and super().__eq__(value)

    @classmethod
    def match(cls, item):
        return "template" in item and super().match(item)


def _load_obj(data):
    yaml = YAML()
    return yaml.load(data)


def _create_parser(data, cwd, file=""):
    obj = _load_obj(data)

    version = obj.get("version", CURRENT_VERSION)
    if not isinstance(version, int):
        raise ConfigError(
            "Invalid version {}".format(version),
            file=file)

    if version == 0:
        parser_cls = Parser
    else:
        raise ConfigError(
            "Version {} is not supported".format(version),
            file=file)

    if file != "":
        parser = parser_cls(obj, cwd, file=file)
    else:
        parser = parser_cls(obj, cwd)

    return parser


class ConfigError(Exception):
    def __init__(self, reason, **meta):
        self.meta = meta

        items = tuple("{}={!r}".format(k, v)
                      for k, v in meta.items() if bool(v))
        if items:
            reason = "{}, ({})".format(reason, ", ".join(items))

        super().__init__(reason)