# importer resolves modules either provided by mimus internal (e.g. `mimus.runtime`)
# or handlers implemented by users.

import os
from os import path as osp

HANDLER_NAMESPACE = "mimus.handler"


def parse_resolve_name(config_path, name):
    """
    Resolve module based on the config path and the name. For instance, the name
    'mimus.handler.example' will be resolved to $CONFIG_PATH/example.py
    """
    if not name.startswith(f"{HANDLER_NAMESPACE}."):
        raise ValueError(f'Moudle name shoule be under "{HANDLER_NAMESPACE}" namespace')

    basedir = osp.basename(config_path)

    resolved_path = basedir
    segments = name.split(".")[2:]
    for segment in segments:
        resolved_path = resolved_path / segment

    if not osp.isfile(resolved_path):
        raise ValueError(f"The resolved path {str(resolved_path)} should be a file.")

    return resolved_path


def get_resolve_name(root, path):
    relpath = osp.relpath(path, start=root)
    relpath_segments = relpath.split(os.sep)

    if relpath_segments[0] == "..":
        raise ValueError('"root" should be one of the parent paths of "path"')

    return f'{HANDLER_NAMESPACE}.{".".join(relpath_segments)}'


class ModuleFinder:
    """
    Meta path finder for modules under "mimus.handler" namespace.
    """

    # def __init__(self, root):
    #     self.root = osp.Path(root).resolve()

    def find_spec(self, fullname, path, target=None):
        if fullname == HANDLER_NAMESPACE:
            return (None, tuple("/tmp", ))

        return None

    def find_loader()
