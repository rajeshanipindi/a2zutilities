from fastapi.testclient import TestClient
import main
import pytest

@pytest.fixture(scope="session")
def client():
    with TestClient(main.app) as client:
        yield client