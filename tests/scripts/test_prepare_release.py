import pytest

from scripts.prepare_release import validate_version


@pytest.mark.parametrize("value", ["0.3.0", "v1.2.3", "1", "1.2.3.4", "65535.0"])
def test_validate_version(value: str) -> None:
    assert validate_version(value) == value.removeprefix("v")


@pytest.mark.parametrize("value", ["", "v", "1.2.3.4.5", "1.02", "1.2-beta", "65536.0", "0.0"])
def test_validate_version_rejects_invalid_chromium_versions(value: str) -> None:
    with pytest.raises(ValueError, match="version"):
        validate_version(value)
