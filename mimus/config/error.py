class ConfigError(Exception):
    def __init__(self, reason, **meta):
        self.meta = meta

        items = tuple("{}={!r}".format(k, v) for k, v in meta.items() if bool(v))
        if items:
            reason = "{}, ({})".format(reason, ", ".join(items))

        super().__init__(reason)
