import pytest

from core.session_context import reset_session


@pytest.fixture(autouse=True)
def reset_session_fixture():
    """Asegura que cada prueba comienza con sesión y trazas limpias."""
    reset_session()
    yield
    reset_session()
