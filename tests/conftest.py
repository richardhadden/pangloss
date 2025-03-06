import pytest

from pangloss.model_config.model_manager import ModelManager


@pytest.fixture(scope="function", autouse=True)
def reset_model_manager():
    ModelManager._reset()
