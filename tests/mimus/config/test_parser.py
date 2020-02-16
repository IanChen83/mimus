import os
from pathlib import Path
from types import SimpleNamespace as Case
import pytest

from ruamel.yaml import YAML

from mimus.config.parser import (
    Parser,
    ConfigFile,
    ImportItem,
    StackItem,
    StackServiceItem,
    TemplateServiceItem,
    BasicServiceItem,
    ConfigError,
)


class Test_Parser:
    def test_parse_and_register_config(self, datadir):
        """
        Test if Parser.parse_and_register_config inserts a new config into
        Parser.configs with resolved file path as key.
        """
        file_path = datadir / "test_parse_root.yml"
        resovled_path = str(file_path.resolve())

        parser = Parser()
        config = parser.parse_and_register_config("", datadir, str(file_path))

        assert len(parser.configs) == 1
        assert parser.configs[resovled_path] is config
        assert config.cwd == datadir.resolve()
        assert len(config.imports) == 0
        assert len(config.services) == 0

    def test_parse_imported_config(self, datadir):
        """
        Test if Parser.parse_and_register_config will not insert a new config
        into Parser.configs if the file path already exists.
        """
        file_path = datadir / "test_parse_root.yml"
        resovled_path = str(file_path.resolve())

        parser = Parser()
        parser.configs[resovled_path] = ConfigFile.loads("", datadir.resolve())
        config = parser.parse_and_register_config("", datadir, str(file_path))

        assert len(parser.configs) == 1
        assert parser.configs[resovled_path] is config
        assert config.cwd == datadir.resolve()
        assert len(config.imports) == 0
        assert len(config.services) == 0

    def test_register_imports(self, datadir):
        """
        Test if Parser.register_import works as expected.
        """

        file_path = datadir / "test_parse_root.yml"
        file_path.touch()

        cases = [
            Case(imports=[ImportItem(path=file_path)]),
            Case(
                imports=[
                    ImportItem(path=file_path.resolve()),
                    ImportItem(path=file_path),
                ],
            ),
        ]

        for case in cases:
            parser = Parser()
            for inc in case.imports:
                parser.register_import(inc)

            assert len(parser.imports) == 1
            assert parser.imports[file_path] == ImportItem(path=file_path)

    def test_register_service(self):
        """
        Test if Parser.register_service works as expected.
        """

        parser = Parser()
        service = BasicServiceItem(name="name", path="path", handler="")
        parser.register_service(service)

        assert len(parser.services) == 1
        assert parser.services["name"] == service

    def test_register_duplicate_service(self):
        """
        Test if Parser.register_service raises exception when
        a service with the same name already exists.
        """

        parser = Parser()
        service = BasicServiceItem(name="name", path="path", handler="",)
        parser.services["name"] = TemplateServiceItem(
            name="name", template="template", handler="",
        )
        with pytest.raises(ConfigError) as excinfo:
            parser.register_service(service)

        assert str(excinfo.value) == "Duplicate service name 'name' found"

    def test_parse(self, datadir):
        root_path = datadir / "test_parse_root.yml"
        included_path = datadir / "test_parse_include.yml"

        with open(root_path) as f:
            content_root = f.read()
        config_root = ConfigFile.loads(content_root, datadir)

        with open(included_path) as f:
            content_included = f.read()
        config_included = ConfigFile.loads(content_included, datadir)

        parser = Parser.parse(content_root, datadir, str(root_path))
        assert parser.root is parser.configs[str(root_path.resolve())]
        assert parser.services == dict(
            name=BasicServiceItem(name="name", handler="handler"),
            name2=TemplateServiceItem(name="name2", template="name"),
            included_service=BasicServiceItem(name="included_service"),
        )
        assert parser.imports == {
            included_path: ImportItem(path=included_path),
        }
        assert parser.stacks == {
            "example_stack": StackItem(name="example_stack", services=("name",)),
            "included_stack": StackItem(
                name="included_stack", services=("included_service",)
            ),
        }
        assert parser.configs == {
            str(root_path.resolve()): config_root,
            str(included_path.resolve()): config_included,
        }

    def test_iter_service(self, datadir):
        root_path = datadir / "test_parse_root.yml"

        with open(root_path) as f:
            content_root = f.read()
        parser = Parser.parse(content_root, datadir, str(root_path))
        assert list(parser.iter_service()) == [
            BasicServiceItem(name="included_service"),
            BasicServiceItem(name="name", handler="handler"),
            BasicServiceItem(name="name2", handler="handler"),
        ]

    def test_resolve_template(self):
        parser = Parser()
        parser.services["template"] = BasicServiceItem(
            name="template", handler="template_handler"
        )

        result = parser.resolve_template(
            TemplateServiceItem(name="derived", port=80, template="template")
        )

        assert result == BasicServiceItem(
            name="derived", port=80, handler="template_handler"
        )

    def test_resolve_template_not_found(self):
        parser = Parser()
        with pytest.raises(ConfigError) as excinfo:
            parser.resolve_template(
                TemplateServiceItem(name="derived", port=80, template="template")
            )

        assert (
            str(excinfo.value)
            == "Cannot find template 'template' for service 'derived'"
        )

    def test_resolve_stack(self):
        parser = Parser()
        parser.stacks["stack"] = StackItem(name="stack", services=["service1"])
        parser.services["service1"] = BasicServiceItem(name="service1")

        result = parser.resolve_stack(StackServiceItem(stack="stack"))
        assert result == [BasicServiceItem(name="service1")]

    def test_resolve_stack_not_found(self):
        parser = Parser()
        parser.stacks["stack"] = StackItem(name="stack", services=["service1"])

        with pytest.raises(ConfigError) as excinfo:
            parser.resolve_stack(StackServiceItem(stack="stack"))

        assert (
            str(excinfo.value)
            == "Cannot find service 'service1' defined in stack 'stack'"
        )


class Test_Config:
    def test_init(self, datadir):
        """
        Test if ConfigFile.__init__ works as expected.
        """

        file_path = datadir / "test_parse_root.yml"
        file_path.touch()

        file_path_str = str(file_path)

        obj = f"""
version: 0
imports:
    - "{file_path_str}"

stacks:
    - name: example_stack
      services:
        - name

services:
    - stack: example_stack
    - name: name
      handler: handler
    - name: name2
      template: name
"""

        config = ConfigFile.loads(obj, datadir)

        assert config.cwd == datadir
        assert config.imports == [ImportItem(path=file_path)]
        assert config.stacks == [StackItem(name="example_stack", services=["name"])]
        assert config.services == [
            StackServiceItem(stack="example_stack"),
            BasicServiceItem(name="name", handler="handler"),
            TemplateServiceItem(name="name2", template="name"),
        ]

    def test_version(self, datadir):
        """
        Test if we validate version in config
        """

        cases = [
            Case(
                content="""
version: 0
            """,
                exception="",
            ),
            Case(
                content="""
version: "0"
                """,
                exception="Invalid version type 'str'",
            ),
            Case(
                content="""
version: -1
                """,
                exception="Unsupported config version '-1'",
            ),
        ]

        for case in cases:
            if case.exception:
                with pytest.raises(ConfigError) as excinfo:
                    ConfigFile.loads(case.content, datadir)

                assert case.exception in str(excinfo.value)
            else:
                ConfigFile.loads(case.content, datadir)

    def test_unknown_service_definition(self, datadir):
        """
        Test if we raise error if we meet unexpected service
        """
        content = """
services:
    - unexpected: service
"""

        with pytest.raises(ConfigError) as excinfo:
            ConfigFile.loads(content, datadir)

        assert (
            str(excinfo.value)
            == """Unknown service definition:
  unexpected: service
"""
        )


class Test_ImportItem:
    def test_init(self, datadir):
        """
        Test if ImportItem.__init__ works as expected.
        """

        item = ImportItem(path=datadir / "test_parse_root.yml")

        assert item.path.samefile(datadir / "test_parse_root.yml")

    def test_init_exception(self):
        """
        Test if ImportItem.__init__ raises exception on malformed inputs.
        """

        cases = [
            Case(kwargs={}, exception="'path' is a required field",),
            Case(
                kwargs=dict(path=Path("non-existed-file")),
                exception="should point to a file",
            ),
        ]

        for case in cases:
            with pytest.raises(ConfigError) as excinfo:
                ImportItem(**case.kwargs)

            assert case.exception in str(excinfo.value)


class Test_StackItem:
    def test_init(self):
        """
        Test if StackItem.__init__ works as expected.
        """

        item = StackItem(name="name", services=["service1"])

        assert item.name == "name"
        assert item.services == ["service1"]

    def test_init_exception(self):
        """
        Test if ImportItem.__init__ raises exception on malformed inputs.
        """

        cases = [
            Case(kwargs=dict(), exception="'name' is a required field",),
            Case(
                kwargs=dict(name="name", services=dict()),
                exception="services should be of type sequence",
            ),
        ]

        for case in cases:
            with pytest.raises(ConfigError) as excinfo:
                StackItem(**case.kwargs)

            assert case.exception in str(excinfo.value)


class Test_BasicServiceItem:
    def test_init(self):
        """
        Test if BasicServiceItem.__init__ works as expected.
        """
        service = BasicServiceItem(
            name="name",
            host="host",
            path="path",
            port=80,
            protocol="protocol",
            handler="handler",
        )

        assert service.name == "name"
        assert service.host == "host"
        assert service.path == "path"
        assert service.port == 80
        assert service.handler == "handler"
        assert service.protocol == "protocol"
        assert service.protocol_attrs == {}

    def test_empty_name(self):
        """
        Test if BasicServiceItem() raises exception when passed with
        empty name.
        """

        with pytest.raises(Exception) as excinfo:
            BasicServiceItem(name="", handler="handler")

        assert "name should be a non-empty string" in str(excinfo.value)


class Test_TemplateServiceItem:
    def test_no_template(self):
        """
        Test if TemplateServiceItem() raises exception when passed with
        unexpected field.
        """

        with pytest.raises(ConfigError) as excinfo:
            TemplateServiceItem(name="name", handler="")

        assert "'template' is a required field" in str(excinfo.value)

    def test_empty_template(self):
        """
        Test if TemplateServiceItem() raises exception when passed with
        empty template.
        """

        with pytest.raises(ConfigError) as excinfo:
            TemplateServiceItem(
                name="name", template="", handler="",
            )

        assert "template should be a non-empty string" in str(excinfo.value)


class Test_StackServiceItem:
    def test_empty(self):
        """
        Test if StackServiceItem() raises exception when passed with
        unexpected field.
        """

        with pytest.raises(ConfigError) as excinfo:
            StackServiceItem(stack="")

        assert "stack should be a non-empty string" in str(excinfo.value)
