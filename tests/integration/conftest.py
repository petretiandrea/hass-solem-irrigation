"""Fixtures for Home Assistant integration tests."""
import pytest



@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow loading the local integration."""
    yield
