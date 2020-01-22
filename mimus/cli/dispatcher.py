import sys
from inspect import getdoc, isclass

from docopt import docopt, DocoptExit

from .error import CommandError, CommandNotFoundError, ArgumentError


class Dispatcher:
    def __init__(self, command, posarg_name="<command>", restarg_name="<args>"):
        self.root = command
        self.version = getattr(command, "__version__", None)
        self._posarg_name = posarg_name
        self._restarg_name = restarg_name

    def run(self, argv):
        return self.run_command(self.root, argv)

    def run_command(self, command, argv):
        doc = getdoc(command) or ""
        doc = doc.strip("\n")

        # In 'delegate_mode', we will use posarg_name and restarg_name to delegate
        # arguments to the sub-command. We assume a class is a Command.
        delegate_mode = getattr(command, "delegate_mode", isclass(command))

        # Note that if the doc-string is invalid, calling docopt() will raise
        # docopt.DocoptLanguageError.
        try:
            options = docopt(doc, argv=argv, help=False, options_first=delegate_mode)
        except DocoptExit:
            raise CommandError("Invalid arguments.\n\n" + doc)

        # If we have '--help' in doc-string and docopt catches it,
        # we print help message for the current command and exit.
        if options.get("--help", False) or options.get("-h", False):
            if doc:
                print(doc)
            sys.exit()

        # If we have '--version' in doc-string and docopt catches it,
        # we print version and exit.
        if options.get("--version", False):
            version = getattr(command, "__version__", self.version)
            if version is None:
                raise ArgumentError(command, "--version")

            print(version)
            sys.exit()

        # If we are in delegate_mode, and docopt catches the command, we delegate
        # the arguements to the sub-command.
        if delegate_mode and options.get(self._posarg_name, ""):
            key = options.get(self._posarg_name, "").replace("-", "_")
            if key.startswith("_"):
                raise ArgumentError(command, key)

            command = command(options)
            if not hasattr(command, key):
                raise CommandNotFoundError(command, key)

            next_command = getattr(command, key)
            next_argv = options.get(self._restarg_name)
            return self.run_command(next_command, next_argv)

        # Since we cannot delegate the command, if the command is a
        # callable, we handle it.
        if callable(command):
            return command(options)

        raise ArgumentError(
            command, "Cannot find handler for arguments: '{}'".format(" ".join(argv))
        )
