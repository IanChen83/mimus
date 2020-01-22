from unittest import mock

import pytest

from mimus.cli.dispatcher import Dispatcher
from mimus.cli.error import CommandNotFoundError, CommandError, ArgumentError


class LeafCommand:
    """LeafCommand

    Usage:
        leaf [options]
        leaf [options] <command> [<args>...]

    Options:
        --flag         Test flag
        --help         Print help message and exit
        --version      Print version and exit

    Available commands include:
        leaf-handler
    """

    def __init__(self, options):
        self.options = options
        assert options.get("--flag") is True
        assert options.get("<command>") == "leaf-handler"

    def leaf_handler(self, options):
        """leaf-handler

        Usage:
          leaf-handler
        """

        return "leaf-handler"


class RootCommand:
    """RootCommand is the root command

    Usage:
        root [options]
        root [options] <command> [<args>...]

    Options:
        --root-flag    Test Root flag
        --help         Print help message and exit
        --version      Print version and exit

    Available commands include:
        leaf
        handler
    """

    __version__ = "RootCommand version"

    def __init__(self, options):
        self.options = options

    def handler(self, options):
        """handler

        Usage:
            handler [--version]

        Options:
            --version      Print version and exit
        """
        return "handler"

    leaf = LeafCommand


def test_command_not_found():
    dispatcher = Dispatcher(RootCommand)
    with pytest.raises(CommandNotFoundError) as excinfo:
        dispatcher.run(["not_found"])

    assert "not found" in str(excinfo.value)


def test_command_error():
    dispatcher = Dispatcher(RootCommand)
    with pytest.raises(CommandError) as excinfo:
        dispatcher.run(["leaf", "--invalid-flag"])

    assert "Invalid arguments." in str(excinfo.value)


def test_subcommand_starts_with_underline():
    dispatcher = Dispatcher(RootCommand)
    with pytest.raises(ArgumentError) as excinfo:
        dispatcher.run(["__init__", "--invalid-flag"])

    assert "Unexpected argument" in str(excinfo.value)


def test_leaf_command():
    dispatcher = Dispatcher(RootCommand)
    assert "leaf-handler" == dispatcher.run(["leaf", "--flag", "leaf-handler"])


def test_help(capsys):
    dispatcher = Dispatcher(RootCommand)
    with pytest.raises(SystemExit) as excinfo:
        dispatcher.run(["--help"])

    captured = capsys.readouterr()

    assert excinfo.value is not None
    assert "RootCommand is the root command" in captured.out


def test_version_in_leaf(capsys):
    dispatcher = Dispatcher(RootCommand)
    with pytest.raises(SystemExit) as excinfo:
        dispatcher.run(["handler", "--version"])

    captured = capsys.readouterr()

    assert excinfo.value is not None
    assert "RootCommand version" in captured.out
