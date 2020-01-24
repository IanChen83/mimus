import os
from pathlib import Path
from types import SimpleNamespace as Case
import pytest

from mimus.parser import (
    Parser,
    Config,
    IncludeItem,
    StackServiceItem,
    TemplateServiceItem,
    ServiceItem,
    ConfigError,
)


class Test_Parser:
    def test_parse_config(self, datadir):
        """
        Test if Parser.parse_config inserts a new config into
        Parser.configs with resolved file path as key.
        """
        file_path = datadir / "test_parse_root.yml"
        resovled_path = str(file_path.resolve())

        parser = Parser()
        config = parser.parse_config("", datadir, str(file_path))

        assert len(parser.configs) == 1
        assert parser.configs[resovled_path] is config
        assert config.file == resovled_path
        assert config.cwd == datadir.resolve()
        assert len(config.includes) == 0
        assert len(config.services) == 0

    def test_parse_included_config(self, datadir):
        """
        Test if Parser.parse_config will not insert a new config into
        Parser.configs if the file path already exists.
        """
        file_path = datadir / "test_parse_root.yml"
        resovled_path = str(file_path.resolve())

        parser = Parser()
        parser.configs[resovled_path] = Config(
            {}, datadir.resolve(), file=resovled_path
        )
        config = parser.parse_config("", datadir, str(file_path))

        assert len(parser.configs) == 1
        assert parser.configs[resovled_path] is config
        assert config.file == resovled_path
        assert config.cwd == datadir.resolve()
        assert len(config.includes) == 0
        assert len(config.services) == 0

    def test_register_include(self, datadir):
        """
        Test if Parser.register_include works as expected.
        """

        file_path = datadir / "test_parse_root.yml"
        file_path.touch()

        cases = [
            Case(includes=[IncludeItem("name", file_path)]),
            Case(
                includes=[
                    IncludeItem("name", file_path.resolve()),
                    IncludeItem("name", file_path),
                ],
            ),
        ]

        for case in cases:
            parser = Parser()
            for inc in case.includes:
                parser.register_include(inc)

            assert len(parser.includes) == 1
            assert parser.includes["name"] == IncludeItem("name", file_path)

    def test_register_duplicate_include(self, datadir):
        """
        Test if Parser.register_include raises exception when
        a include with the same name but different path already exists.
        """

        file_path = datadir / "empty.yml"
        file_path2 = datadir / "empty2.yml"
        file_path.touch()
        file_path2.touch()

        parser = Parser()
        parser.includes["name"] = IncludeItem("name", file_path)

        with pytest.raises(ConfigError) as excinfo:
            parser.register_include(IncludeItem("name", file_path2))

        assert "Duplicate include name 'name' but differnt config path" in str(
            excinfo.value
        )

    def test_register_service(self):
        """
        Test if Parser.register_service works as expected.
        """

        parser = Parser()
        service = ServiceItem(dict(name="name", path="path",), file="file")
        parser.register_service(service)

        assert len(parser.services) == 1
        assert parser.services["name"] == service

    def test_register_duplicate_service(self):
        """
        Test if Parser.register_service raises exception when
        a service with the same name already exists.
        """

        parser = Parser()
        service = ServiceItem(dict(name="name", path="path",), file="file")
        parser.services["name"] = TemplateServiceItem(
            dict(name="name", template="template",), file="file"
        )
        with pytest.raises(ConfigError) as excinfo:
            parser.register_service(service)

        assert (
            str(excinfo.value) == "Duplicate service name 'name' found in file and file"
        )

    def test_parse(self, datadir):
        """
        Test Parser.parse works as expected.
        """
        file_path = datadir / "test_parse_root.yml"
        root_path = str(file_path.resolve())
        include_path = str((datadir / "test_parse_include.yml").resolve())

        with open(str(file_path)) as f:
            data = f.read()
        parser = Parser.parse(data, datadir, str(file_path))

        assert len(parser.configs) == 2
        assert parser.root is parser.configs[root_path]

        root_config = parser.configs[root_path]
        assert root_config.file == root_path
        assert root_config.cwd == datadir
        assert root_config.includes == [
            IncludeItem("test_parse_include", datadir / "test_parse_include.yml")
        ]
        assert root_config.services == [
            ServiceItem(dict(name="name")),
            StackServiceItem(dict(stack="test_parse_include")),
        ]
        include_config = parser.configs[include_path]
        assert include_config.file == include_path
        assert include_config.cwd == datadir
        assert len(include_config.includes) == 0
        assert len(include_config.services) == 0

        assert len(parser.services) == 1
        assert parser.services["name"] == ServiceItem(dict(name="name"))
        assert len(parser.includes) == 1
        assert parser.includes["test_parse_include"] == IncludeItem(
            "test_parse_include", datadir / "test_parse_include.yml"
        )

    def test_iter_service(self, datadir):
        file_path = datadir / "test_parse_root.yml"
        resolved_path = str(file_path.resolve())

        parser = Parser.parse("", datadir, "")
        parser.includes["include"] = IncludeItem("include", file_path)
        parser.configs[resolved_path] = Config({}, datadir)
        parser.configs[resolved_path].services = [
            ServiceItem(dict(name="include_service")),
        ]
        parser.services["prototype2"] = ServiceItem(
            dict(
                name="prototype2",
                host="prototype2_host",
                path="prototype2_path",
                port=80,
                protocol="prototype2_protocol",
                method="prototype2_method",
                handler="prototype2_handler",
                tlskey="prototype2_tlskey",
                tlscert="prototype2_tlscert",
            )
        )
        parser.services["prototype1"] = TemplateServiceItem(
            dict(name="prototype1", template="prototype2", host="prototype1_host"),
        )
        parser.root = Config({}, datadir)
        parser.root.services = [
            TemplateServiceItem(
                dict(name="template", template="prototype1", path="template_path")
            ),
            StackServiceItem(dict(stack="include")),
        ]
        assert list(parser.iter_service()) == [
            ServiceItem(
                dict(
                    name="template",
                    host="prototype1_host",
                    path="template_path",
                    port=80,
                    protocol="prototype2_protocol",
                    method="prototype2_method",
                    handler="prototype2_handler",
                    tlskey="prototype2_tlskey",
                    tlscert="prototype2_tlscert",
                )
            ),
            ServiceItem(dict(name="include_service")),
        ]

    def test_resolve_template(self, datadir):
        """
        Test if Parser.resolve_template works as expected.
        """
        file_path = datadir / "test_parse_root.yml"

        parser = Parser.parse("", datadir, "")
        parser.services["prototype"] = ServiceItem(
            dict(
                name="prototype",
                host="prototype_host",
                path="prototype_path",
                port=80,
                protocol="prototype_protocol",
                method="prototype_method",
                handler="prototype_handler",
                tlskey="prototype_tlskey",
                tlscert="prototype_tlscert",
            )
        )

        template = TemplateServiceItem(
            dict(name="template", template="prototype", host="host")
        )
        expected = ServiceItem(
            dict(
                name="template",
                host="host",
                path="prototype_path",
                port=80,
                protocol="prototype_protocol",
                method="prototype_method",
                handler="prototype_handler",
                tlskey="prototype_tlskey",
                tlscert="prototype_tlscert",
            )
        )

        result = parser.resolve_template(template)
        assert result == expected
        assert result.inherits[0] == "template:prototype"

    def test_resolve_unknown_template(self, datadir):
        """
        Test if Parser.resolve_template raises exception if the template
        name is not found.
        """
        file_path = datadir / "test_parse_root.yml"
        parser = Parser.parse("", datadir, str(file_path))

        with pytest.raises(ConfigError) as excinfo:
            parser.resolve_template(
                TemplateServiceItem(dict(name="name", template="unknown"))
            )

        assert "Cannot find template 'unknown' for service 'name'" in str(excinfo.value)

    def test_resolve_stack(self, datadir):
        file_path = datadir / "test_parse_root.yml"
        resolved_path = str(file_path.resolve())

        parser = Parser.parse("", datadir, "")
        parser.includes["test_parse_root"] = IncludeItem("test_parse_root", file_path)
        parser.configs[resolved_path] = Config({}, datadir)
        parser.configs[resolved_path].services = [
            ServiceItem(dict(name="name")),
            StackServiceItem(dict(stack="test_parse_include")),
        ]

        results = parser.resolve_stack(StackServiceItem(dict(stack="test_parse_root")))
        assert results == [
            ServiceItem(dict(name="name")),
            StackServiceItem(dict(stack="test_parse_include")),
        ]
        assert results[0].inherits[0] == "stack:test_parse_root"
        assert results[1].inherits[0] == "stack:test_parse_root"

    def test_resolve_unknown_stack(self, datadir):
        file_path = datadir / "test_parse_root.yml"
        parser = Parser.parse("", datadir, "")

        with pytest.raises(ConfigError) as excinfo:
            parser.resolve_stack(StackServiceItem(dict(stack="unknown")))

        assert "Cannot find stack with name 'unknown'" in str(excinfo.value)


class Test_Config:
    def test_init(self, datadir):
        """
        Test if Config.__init__ works as expected.
        """

        file_path = datadir / "test_parse_root.yml"
        file_path.touch()

        obj = {
            "includes": [{"name": "include_1", "path": str(file_path),}],
            "services": [{"stack": "stack",}, {"name": "name", "host": "host",}],
        }

        config = Config(obj, datadir)

        assert len(config.includes) == 1
        assert config.includes[0] == IncludeItem("include_1", file_path)

        assert len(config.services) == 2
        assert config.services[0] == StackServiceItem(dict(stack="stack"))
        assert config.services[1] == ServiceItem(dict(name="name", host="host"))

    def test_init_exception(self, datadir):
        """
        Test if Config.__init__ raises exception on malformed inputs.
        """

        file_path = datadir / "test_parse_root.yml"
        file_path.touch()

        cases = [
            Case(
                args=({"includes": [{"name": "include_1",}],}, datadir),
                exception="includes.item should have attribute 'name'",
            ),
            Case(
                args=({"includes": [{"path": str(file_path),}],}, datadir),
                exception="includes.item should have attribute 'path'",
            ),
            Case(
                args=({"services": [{}],}, datadir),
                exception="idoesn't match any service definition",
            ),
        ]

        for case in cases:
            with pytest.raises(ConfigError) as excinfo:
                Config(*case.args)

                assert case.exception in str(excinfo.value)


class Test_IncludeItem:
    def test_init(self):
        """
        Test if IncludeItem.__init__ works as expected.
        """

        item = IncludeItem("name", Path("mimus/parser.py"), file="file")

        assert item.name == "name"
        assert item.path.samefile(Path("mimus/parser.py"))
        assert item.file == "file"

    def test_init_exception(self):
        """
        Test if IncludeItem.__init__ raises exception on malformed inputs.
        """

        cases = [
            Case(
                args=("", Path("mimus/parser.py")),
                kwargs={},
                exception="includes.item.name cannot be an empty string",
            ),
            Case(
                args=("name", Path("non-existed-file")),
                kwargs=dict(file="file"),
                exception="should point to a config file",
            ),
        ]

        for case in cases:
            with pytest.raises(ConfigError) as excinfo:
                IncludeItem(*case.args, **case.kwargs)

                assert case.exception in str(excinfo.value)

    def test_repr(self):
        """
        Test if IncludeItem.__repr__ works as expected.
        """

        cases = [
            Case(
                args=("name", Path("mimus/parser.py")),
                kwargs={},
                output="IncludeItem(name='name', path=",
            ),
            Case(
                args=("name", Path("mimus/parser.py")),
                kwargs=dict(file="file"),
                output="IncludeItem(name='name', path=",
            ),
        ]

        for case in cases:
            assert case.output in repr(IncludeItem(*case.args, **case.kwargs))


class Test_StackServiceItem:
    def test_repr(self):
        """
        Test if StackServiceItem.__repr__ works as expected.
        """

        cases = [
            Case(
                args=(dict(stack="stack"),),
                kwargs={},
                output="StackServiceItem(stack='stack')",
            ),
            Case(
                args=(dict(stack="stack"),),
                kwargs=dict(file="file"),
                output="StackServiceItem(stack='stack', file='file')",
            ),
        ]

        for case in cases:
            assert repr(StackServiceItem(*case.args, **case.kwargs)) == case.output

    def test_unexpected_field(self):
        """
        Test if StackServiceItem() raises exception when passed with
        unexpected field.
        """

        with pytest.raises(ConfigError) as excinfo:
            StackServiceItem(dict(stack="stack", unexpected="unexpected"))

        assert "Unexpected field(s) when specifying stack 'stack': unexpected" in str(
            excinfo.value
        )

    def test_empty_satck(self):
        """
        Test if StackServiceItem() raises exception when passed with
        empty stack.
        """

        with pytest.raises(ConfigError) as excinfo:
            StackServiceItem(dict(stack="",))

        assert "If specified, services.item.stack cannot be an empty string" in str(
            excinfo.value
        )

    def test_match(self):
        """
        Test if StackServiceItem.match matches items with 'stack' field.
        """

        cases = [
            Case(input=dict(stack="stack"), output=True,),
            Case(input=dict(stack="stack", other="other"), output=True,),
            Case(input=dict(nostack="nostack"), output=False,),
        ]

        for case in cases:
            assert StackServiceItem.match(case.input) == case.output


class Test_TemplateServiceItem:
    def test_repr(self):
        """
        Test if TemplateServiceItem.__repr__ works as expected.
        """

        cases = [
            Case(
                args=(dict(name="name", template="template"),),
                kwargs={},
                output="TemplateServiceItem(name='name', template='template')",
            ),
            Case(
                args=(dict(name="name", template="template"),),
                kwargs=dict(file="file"),
                output="TemplateServiceItem(name='name', template='template', file='file')",
            ),
        ]

        for case in cases:
            assert repr(TemplateServiceItem(*case.args, **case.kwargs)) == case.output

    def test_unexpected_field(self):
        """
        Test if TemplateServiceItem() raises exception when passed with
        unexpected field.
        """

        with pytest.raises(ConfigError) as excinfo:
            TemplateServiceItem(
                dict(name="name", template="template", unexpected="unexpected",)
            )

        assert "Unexpected field(s) when specifying service 'name': unexpected" in str(
            excinfo.value
        )

    def test_empty_template(self):
        """
        Test if TemplateServiceItem() raises exception when passed with
        empty template.
        """

        with pytest.raises(ConfigError) as excinfo:
            TemplateServiceItem(dict(name="name", template="",))

        assert "If specified, services.item.template cannot be an empty string" in str(
            excinfo.value
        )

    def test_match(self):
        """
        Test if TemplateServiceItem.match matches items with 'name' and 'template fields.
        """

        cases = [
            Case(input=dict(name="name", template="template"), output=True,),
            Case(input=dict(name="name"), output=False,),
            Case(input=dict(template="template"), output=False,),
        ]

        for case in cases:
            assert TemplateServiceItem.match(case.input) == case.output


class Test_ServiceItem:
    def test_init(self):
        """
        Test if ServiceItem.__init__ works as expected.
        """
        service = ServiceItem(
            dict(
                name="name",
                host="host",
                path="path",
                port=80,
                protocol="protocol",
                method="method",
                handler="handler",
                tlskey="tlskey",
                tlscert="tlscert",
            ),
            file="file",
        )

        assert service.name == "name"
        assert service.host == "host"
        assert service.path == "path"
        assert service.port == 80
        assert service.protocol == "protocol"
        assert service.method == "method"
        assert service.handler == "handler"
        assert service.tlskey == "tlskey"
        assert service.tlscert == "tlscert"

    def test_repr(self):
        """
        Test if ServiceItem.__repr__ works as expected.
        """

        cases = [
            Case(
                args=(dict(name="name"),), kwargs={}, output="ServiceItem(name='name')",
            ),
            Case(
                args=(dict(name="name"),),
                kwargs=dict(file="file"),
                output="ServiceItem(name='name', file='file')",
            ),
        ]

        for case in cases:
            assert repr(ServiceItem(*case.args, **case.kwargs)) == case.output

    def test_unexpected_field(self):
        """
        Test if ServiceItem() raises exception when passed with
        unexpected field.
        """

        with pytest.raises(ConfigError) as excinfo:
            ServiceItem(dict(name="name", unexpected="unexpected",))

        assert "Unexpected field(s) when specifying service 'name': unexpected" in str(
            excinfo.value
        )

    def test_empty_name(self):
        """
        Test if ServiceItem() raises exception when passed with
        empty name.
        """

        with pytest.raises(ConfigError) as excinfo:
            ServiceItem(dict(name=""))

        assert "If specified, services.item.name cannot be an empty string" in str(
            excinfo.value
        )

    def test_match(self):
        """
        Test if ServiceItem.match matches items with 'name' fields.
        """

        cases = [
            Case(input=dict(name="name"), output=True,),
            Case(input=dict(template="template"), output=False,),
        ]

        for case in cases:
            assert ServiceItem.match(case.input) == case.output
