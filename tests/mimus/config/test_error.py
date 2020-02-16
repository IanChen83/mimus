import pytest

from mimus.config.error import ConfigError


class Test_ConfigError:
    def test_no_meta(self):
        with pytest.raises(ConfigError) as excinfo:
            raise ConfigError("reason")

        assert str(excinfo.value) == "reason"

    def test_meta(self):
        with pytest.raises(ConfigError) as excinfo:
            raise ConfigError("reason", meta1="", meta2="meta2", meta3=1)

        assert str(excinfo.value) == "reason (meta2=meta2, meta3=1)"
