import os
from pathlib import Path
from types import SimpleNamespace as Case


def test_get_resolve_name():
    cases = [
        Case(
            config="/config.file",
            name="mimus.handler.qwer",
        ),
    ]
