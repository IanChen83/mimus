import sys
from inspect import getdoc

from .. import (
    __version__ as package_version,
    __name__ as package_name,
)
from .error import CommandError, CommandNotFoundError
from .dispatcher import Dispatcher


class Mimus:
    """Mimus create mock service with ease.

    Usage:
        mimus [options]
        mimus [options] <command> [<args>...]

    Options:
        --verbose, -v  Make mimus verbose
        --help         Print help message and exit
        --version      Print version and exit

    Available commands include:
        up       Start a service
        down     Stop a service
        restart  Restart the service
        config   Validate and view the mimus config file
        help     Get help on a command
        version  Show the mimus version information
    """

    def __init__(self, options):
        if not options.get("<command>", ""):
            raise CommandError("No command is given", Mimus)
        self.global_option = options

    delegate_mode = True
    __version__ = "{} {}".format(package_name, package_version)

    def up(self, options):
        """up starts a service.

        Usage:
            up [options]

            Options:
                --help     Print help message and exit
                --version  Print version and exit
        """
        print(self, options)

    def down(self, options):
        """down stops a service.

        Usage:
            down [options]

            Options:
                --help     Print help message and exit
                --version  Print version and exit
        """
        print(self, options)

    def restart(self, options):
        """restart restarts the service

        Usage:
            restart [options]

            Options:
                --help     Print help message and exit
                --version  Print version and exit
        """
        print(self, options)

    def config(self, options):
        """config validates and views the mimus config file

        Usage:
            config [options]

            Options:
                --help     Print help message and exit
                --version  Print version and exit
        """
        print(self, options)

    def help(self, options):
        """help print the help message of a command

        Usage:
            help <command>
        """
        name = options.get("<command>", "").strip()
        if not name:
            raise CommandError("Command not given.", self.help)
        if name.startswith("_"):
            raise CommandError("Invalid command.")

        fn = getattr(self, name, None)
        if fn is None:
            raise CommandNotFoundError(self.help, name)

        print(getdoc(fn))
        sys.exit()

    def version(self, _):
        """version print mimus version

        Usage:
            version
        """
        print(self.__version__)


def main():
    dispatcher = Dispatcher(Mimus)
    dispatcher.run(sys.argv[1:])
