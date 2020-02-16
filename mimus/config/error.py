from types import SimpleNamespace

__all__ = ("ConfigError",)


class ConfigError(Exception):
    def __init__(self, reason, **meta):
        self.meta = SimpleNamespace(**meta)

        super().__init__(reason)

    def __str__(self):
        if self.meta.__dict__:
            meta = ", ".join(
                f"{k}={v}" for k, v in self.meta.__dict__.items() if bool(v)
            )

            return f"{super().__str__()} ({meta})"

        return super().__str__()
