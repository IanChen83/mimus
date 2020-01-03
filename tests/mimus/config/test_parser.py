import os
from pathlib import Path
from types import SimpleNamespace as Case
import pytest

from mimus.config.parser import (
    Config,
    IncludeItem,
    StackServiceItem,
    TemplateServiceItem,
    ServiceItem,
    ConfigError,
)


class Test_Config:

    def test_init(self, datadir):
        """
        Test if Config.__init__ works as expected.
        """
        obj = {
            "includes": [{
                "name": "include_1",
                "path": str(datadir / "empty.yml"),
            }],
            "services": [{
                "stack": "stack",
            }, {
                "name": "name",
                "host": "host",
            }],
        }

        config = Config(obj, datadir)

        assert len(config.includes) == 1
        assert config.includes[0] == IncludeItem(
            "include_1", datadir / "empty.yml")

        assert len(config.services) == 2
        assert config.services[0] == StackServiceItem(dict(stack="stack"))
        assert config.services[1] == ServiceItem(
            dict(name="name", host="host"))

    def test_init_exception(self, datadir):
        """
        Test if Config.__init__ raises exception on malformed inputs.
        """

        cases = [
            Case(
                args=({
                    "includes": [{
                        "name": "include_1",
                    }],
                }, datadir),
                exception="includes.item should have attribute 'name'",
            ),
            Case(
                args=({
                    "includes": [{
                        "path": str(datadir / "empty.yml"),
                    }],
                }, datadir),
                exception="includes.item should have attribute 'path'",
            ),
            Case(
                args=({
                    "services": [{}],
                }, datadir),
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

        item = IncludeItem("name", Path("mimus/config/parser.py"), file="file")

        assert item.name == "name"
        assert item.path.samefile(Path("mimus/config/parser.py"))
        assert item.file == "file"

    def test_init_exception(self):
        """
        Test if IncludeItem.__init__ raises exception on malformed inputs.
        """

        cases = [
            Case(
                args=("", Path("mimus/config/parser.py")),
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
                args=("name", Path("mimus/config/parser.py")),
                kwargs={},
                output="IncludeItem(name='name', path=",
            ),
            Case(
                args=("name", Path("mimus/config/parser.py")),
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
                args=(dict(stack="stack"), ),
                kwargs={},
                output="StackServiceItem(stack='stack')",
            ),
            Case(
                args=(dict(stack="stack"), ),
                kwargs=dict(file="file"),
                output="StackServiceItem(stack='stack', file='file')",
            ),
        ]

        for case in cases:
            assert repr(StackServiceItem(
                *case.args, **case.kwargs)) == case.output

    def test_unexpected_field(self):
        """
        Test if StackServiceItem() raises exception when passed with
        unexpected field.
        """

        with pytest.raises(ConfigError) as excinfo:
            StackServiceItem(dict(stack="stack", unexpected="unexpected"))

        assert "Unexpected field(s) when specifying stack 'stack': unexpected" in str(
            excinfo.value)

    def test_empty_satck(self):
        """
        Test if StackServiceItem() raises exception when passed with
        empty stack.
        """

        with pytest.raises(ConfigError) as excinfo:
            StackServiceItem(dict(
                stack="",
            ))

        assert "If specified, services.item.stack cannot be an empty string" in str(
            excinfo.value)

    def test_match(self):
        """
        Test if StackServiceItem.match matches items with 'stack' field.
        """

        cases = [
            Case(
                input=dict(stack="stack"),
                output=True,
            ),
            Case(
                input=dict(stack="stack", other="other"),
                output=True,
            ),
            Case(
                input=dict(nostack="nostack"),
                output=False,
            ),
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
                args=(dict(name="name", template="template"), ),
                kwargs={},
                output="TemplateServiceItem(name='name', template='template')",
            ),
            Case(
                args=(dict(name="name", template="template"), ),
                kwargs=dict(file="file"),
                output="TemplateServiceItem(name='name', template='template', file='file')",
            ),
        ]

        for case in cases:
            assert repr(TemplateServiceItem(
                *case.args, **case.kwargs)) == case.output

    def test_unexpected_field(self):
        """
        Test if TemplateServiceItem() raises exception when passed with
        unexpected field.
        """

        with pytest.raises(ConfigError) as excinfo:
            TemplateServiceItem(dict(
                name="name",
                template="template",
                unexpected="unexpected",
            ))

        assert "Unexpected field(s) when specifying service 'name': unexpected" in str(
            excinfo.value)

    def test_empty_template(self):
        """
        Test if TemplateServiceItem() raises exception when passed with
        empty template.
        """

        with pytest.raises(ConfigError) as excinfo:
            TemplateServiceItem(dict(
                name="name",
                template="",
            ))

        assert "If specified, services.item.template cannot be an empty string" in str(
            excinfo.value)

    def test_match(self):
        """
        Test if TemplateServiceItem.match matches items with 'name' and 'template fields.
        """

        cases = [
            Case(
                input=dict(name="name", template="template"),
                output=True,
            ),
            Case(
                input=dict(name="name"),
                output=False,
            ),
            Case(
                input=dict(template="template"),
                output=False,
            ),
        ]

        for case in cases:
            assert TemplateServiceItem.match(case.input) == case.output


class Test_ServiceItem:
    def test_init(self):
        """
        Test if ServiceItem.__init__ works as expected.
        """
        service = ServiceItem(dict(
            name="name",
            host="host",
            path="path",
            port=80,
            protocol="protocol",
            method="method",
            handler="handler",
            tlskey="tlskey",
            tlscert="tlscert",
        ), file="file")

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
                args=(dict(name="name"), ),
                kwargs={},
                output="ServiceItem(name='name')",
            ),
            Case(
                args=(dict(name="name"), ),
                kwargs=dict(file="file"),
                output="ServiceItem(name='name', file='file')",
            ),
        ]

        for case in cases:
            assert repr(ServiceItem(
                *case.args, **case.kwargs)) == case.output

    def test_unexpected_field(self):
        """
        Test if ServiceItem() raises exception when passed with
        unexpected field.
        """

        with pytest.raises(ConfigError) as excinfo:
            ServiceItem(dict(
                name="name",
                unexpected="unexpected",
            ))

        assert "Unexpected field(s) when specifying service 'name': unexpected" in str(
            excinfo.value)

    def test_empty_name(self):
        """
        Test if ServiceItem() raises exception when passed with
        empty name.
        """

        with pytest.raises(ConfigError) as excinfo:
            ServiceItem(dict(name=""))

        assert "If specified, services.item.name cannot be an empty string" in str(
            excinfo.value)

    def test_match(self):
        """
        Test if ServiceItem.match matches items with 'name' fields.
        """

        cases = [
            Case(
                input=dict(name="name"),
                output=True,
            ),
            Case(
                input=dict(template="template"),
                output=False,
            ),
        ]

        for case in cases:
            assert ServiceItem.match(case.input) == case.output
