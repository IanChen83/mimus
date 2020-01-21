from inspect import getdoc

__all__ = (
    "CommandNotFoundError",
    "ArgumentError",
)


def _append_usage(message, command):
    doc = getdoc(command)
    if doc:
        message += "\n\n"
        message += doc
    return message


class CommandError(SystemExit):
    def __init__(self, message, command=None):
        if command and getdoc(command):
            message = message.strip("\n") + "\n\n"
            message += getdoc(command).strip("\n")

        super().__init__(message)


class CommandNotFoundError(SystemExit):
    def __init__(self, command, name):
        message = "Command '{}' not found.".format(name)
        message = _append_usage(message, command)
        super().__init__(message)

        self.command = command


class ArgumentError(SystemExit):
    def __init__(self, command, argv):
        if isinstance(argv, str):
            message = "Unexpected argument: '{}'".format(argv)
        elif isinstance(argv, list):
            message = "Unexpected argument(s): '{}'".format(" ".join(argv))
        else:
            message = "Unexpected argument(s): '{}'".format(argv)

        message = _append_usage(message, command)
        super().__init__(message)

        self.command = command
