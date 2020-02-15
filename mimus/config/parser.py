"""
parser parses config files
"""
from pathlib import Path

from ruamel.yaml import YAML

from .configitem import ConfigItem
from .error import ConfigError

__all__ = (
    "CURRENT_VERSION",
    "SUPPORTED_PARSERS",
    "load",
    "loads",
    "ConfigFile",
    "Parser",
    "StackServiceItem",
    "TemplateServiceItem",
    "BasicServiceItem",
    "ConfigError",
)


CURRENT_VERSION = 0
SUPPORTED_PARSERS = (0,)


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
        self.imports = {}
        self.stacks = {}
        self.configs = {}

    def parse_config(self, content, cwd, file):
        cwd = cwd.resolve()
        if file != "":
            file = str(Path(file).resolve())

        if file not in self.configs:
            self.configs[file] = ConfigFile.loads(content, cwd, file=file)

        return self.configs[file]

    def register_import(self, imp):
        if imp.path not in self.imports:
            self.imports[imp.path] = imp
            return

    def register_stack(self, stack):
        if stack.name not in self.stacks:
            self.stacks[stack.name] = stack
            return

        prev = self.imports[stack.name]
        if prev.services != stack.services:
            err_msg = (
                "Duplicate stack name '{}' but different services list"
                "{} and {} found in {} and {}."
            ).format(stack.name, prev.services, stack.services, prev.file, stack.file)
            raise ConfigError(err_msg)

    def register_service(self, service):
        if service.name not in self.services:
            self.services[service.name] = service
            return

        prev = self.services[service.name]
        if service.file and prev.file:
            err_msg = "Duplicate service name '{}' found in {} and {}".format(
                service.name, service.file, prev.file
            )
        else:
            err_msg = "Duplicate service name '{}' found".format(service.name)
        raise ConfigError(err_msg)

    @classmethod
    def parse(cls, content, cwd, file=""):
        parser = cls()

        config = parser.parse_config(content, cwd, file)
        parser.root = config

        unhandled_imports = list(config.imports)
        while unhandled_imports:
            imp = unhandled_imports.pop(0)

            parser.register_import(imp)
            if str(imp.path) not in parser.configs:
                # If imp.path is already in the config list, we won't
                # parse it (and append imports) again. This allows users
                # to include the same file multiple times with different names.
                with imp.path.open() as f:
                    content = f.read()

                config = parser.parse_config(content, imp.path.parent, str(imp.path))
                unhandled_imports.extend(config.imports)

        for config in parser.configs.values():
            for stack in config.stacks:
                parser.register_stack(stack)

            for service in config.services:
                if hasattr(service, "name"):
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

            elif isinstance(service, BasicServiceItem):
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
        if obj.stack not in self.stacks:
            raise ConfigError(
                "Cannot find stack with name '{}'".format(obj.stack), file=obj.file,
            )

        stack_path = self.stacks[obj.stack].path
        config = self.configs[str(stack_path)]
        results = config.services.copy()

        for service in results:
            service.inherits = ("stack:" + obj.stack, *service.inherits)

        return results


class ConfigFile(
    ConfigItem,
    fields="imports,stacks,services,cwd,file,version",
    defaults=dict(imports=[], stacks=[], services=[], version=CURRENT_VERSION),
):
    """
    Contains imports, stacks, and services definitions. A config item needs to
    define its current folder on the file system so it can reference others
    using relative paths. Normally, the path is the parent folder of the config
    file, but the current folder could be anywhere on the file system.
    """

    def _transform_imports(self, imports):
        return [self._parse_import(item) for item in imports]

    def _transform_stacks(self, stacks):
        return [self._parse_stack(item) for item in stacks]

    def _transform_services(self, services):
        return [self._parse_service(item) for item in services]

    def _validate_version(self, version):
        if not isinstance(version, int):
            raise ConfigError("Invalid version {}".format(version), file=self.file)
        if version not in SUPPORTED_PARSERS:
            raise ConfigError(
                "Unsupported config version {}".format(version), file=self.file
            )

    @classmethod
    def load(cls, f, cwd, *, file=""):
        return cls.loads(f.read(), cwd, file=file)

    @classmethod
    def loads(cls, s, cwd, *, file=""):
        obj = cls._load_obj(s)
        return cls(**obj, cwd=cwd, file=file)

    @staticmethod
    def _load_obj(s):
        yaml = YAML()
        return yaml.load(s) or {}

    def _parse_stack(self, item):
        return StackItem(**item, file=self.file)

    def _parse_import(self, item):
        path = self.cwd.joinpath(item)
        return ImportItem(path=path, file=self.file)

    def _parse_service(self, item):
        if "stack" in item:
            return StackServiceItem(stack=item["stack"], file=self.file)

        if "template" in item and "name" in item:
            item = item.copy()
            item["file"] = self.file
            return TemplateServiceItem.from_dict(item)

        if "name" in item:
            item = item.copy()
            item["file"] = self.file
            return BasicServiceItem.from_dict(item)

        raise ConfigError(
            "Unknown service definition {}".format(item), file=self.file,
        )


#################################################
# Below are the configuration sub-items for each
# field.
#################################################


@staticmethod
def _validate_name(name):
    if isinstance(name, str) and name != "":
        return

    raise ConfigError("name should be a non-empty string")


@staticmethod
def _validate_file(file):
    if file == "" or Path(file).is_file():
        return

    raise ConfigError(f"Field 'file' should point to a file")


@staticmethod
def _transform_inherits(inherits):
    if inherits is None:
        return []
    if isinstance(inherits, (tuple, list)):
        return list(inherits)

    raise ConfigError("Stack inherits should be a sequence")


@staticmethod
def _validate_path(path):
    if isinstance(path, str):
        return

    raise ConfigError("path should be a string")


@staticmethod
def _validate_port(port):
    if isinstance(port, int) and 0 <= port < 65536:
        return

    raise ConfigError("port should be an int in the range of [0, 65535]")


@staticmethod
def _validate_protocol(protocol):
    if isinstance(protocol, str):
        return

    raise ConfigError("protocol should be a string")


@staticmethod
def _transform_protocol_attrs(protocol_attrs):
    if protocol_attrs is None:
        return {}
    if isinstance(protocol_attrs, dict):
        return protocol_attrs

    raise ConfigError("protocol attribute should be either None or a dict")


@staticmethod
def _validate_handler(handler):
    if isinstance(handler, str):
        return handler

    raise ConfigError("handler should be a string")


class ImportItem(ConfigItem, fields="path,file", defaults=dict(file="")):
    """Serve as a reference to another file. `path` has to be a valid path
    pointing to a file.
    """

    _validate_file = _validate_file

    @staticmethod
    def _transform_path(path):
        if not path.is_file():
            raise ConfigError("Field 'path' should point to a file")

        return path.resolve()

    def __eq__(self, obj):
        return self.path.samefile(obj.path)


class StackItem(
    ConfigItem, fields="name,services,file", defaults=dict(services=[], file="")
):
    """A stack that defines a list of services referenced by names.
    """

    _validate_name = _validate_name
    _validate_file = _validate_file

    @staticmethod
    def _transform_services(services):
        if not isinstance(services, (list, tuple)):
            raise ConfigError("services should be of type sequence")

        return list(services)


class BasicServiceItem(
    ConfigItem,
    fields="name,host,path,port,protocol,protocol_attrs,handler,file,inherits",
    defaults=dict(
        host="",
        path="",
        port=0,
        protocol="",
        protocol_attrs=None,
        file="",
        inherits=None,
    ),
):
    """Serve as the basic service configuration item. Every service item will
    be eventually resolved to this type.
    """

    _validate_name = _validate_name
    _validate_path = _validate_path
    _validate_port = _validate_port
    _validate_protocol = _validate_protocol
    _transform_protocol_attrs = _transform_protocol_attrs
    _validate_handler = _validate_handler

    _validate_file = _validate_file
    _transform_inherits = _transform_inherits


class TemplateServiceItem(
    ConfigItem,
    fields="name,template,host,path,port,protocol,protocol_attrs,handler,file,inherits",
    defaults=dict(
        host="",
        path="",
        port=0,
        protocol="",
        protocol_attrs=None,
        file="",
        inherits=None,
    ),
):
    """A kind of service item based on the template. Any value that is not
    zero value will overwrite the value of the same attribute in the template.
    """

    _validate_name = _validate_name
    _validate_path = _validate_path
    _validate_port = _validate_port
    _validate_protocol = _validate_protocol
    _transform_protocol_attrs = _transform_protocol_attrs
    _validate_handler = _validate_handler

    _validate_file = _validate_file
    _transform_inherits = _transform_inherits

    @staticmethod
    def _validate_template(template):
        if isinstance(template, str) and template != "":
            return

        raise ConfigError("template should be a non-empty string")


class StackServiceItem(
    ConfigItem, fields="stack,file,inherits", defaults={"file": "", "inherits": None}
):
    """A kind of service item that resolves to a stack, which is a list of
    service items.
    """

    _validate_file = _validate_file
    _transform_inherits = _transform_inherits

    @staticmethod
    def _validate_stack(stack):
        if isinstance(stack, str) and stack != "":
            return

        raise ConfigError("stack should be a non-empty string")
