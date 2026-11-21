from pathlib import Path

import pytest

from aurai_workspace.realm import load_realm

REALM_FILE = Path(__file__).resolve().parent.parent / "realm" / "aurai-realm.yaml"


@pytest.fixture
def realm_file() -> Path:
    return REALM_FILE


@pytest.fixture
def realm() -> dict:
    return load_realm(REALM_FILE)
