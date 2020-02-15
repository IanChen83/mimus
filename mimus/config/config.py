"""
config handles loading configuration from file system.
"""

__all__ = (
    "Config",
    "Service",
)


class Config:
    """
    Config stores and validates configuration.
    """

    def __init__(self, *, services, includes, path, version):
        super().__init__()

        self.path = path
        self.version = version
        self.includes = includes or {}
        self.services = services or []
        self._service_map = {srv.get("name"): srv for srv in self.services}


class Service:
    """
    Service stores service definition.
    """
