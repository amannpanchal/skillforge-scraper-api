import pytest
from fastapi import HTTPException

from app.main import _validate_public_url


def test_rejects_localhost():
    with pytest.raises(HTTPException) as error:
        _validate_public_url("http://localhost:8000")
    assert error.value.status_code == 400


def test_rejects_private_ip():
    with pytest.raises(HTTPException) as error:
        _validate_public_url("http://127.0.0.1")
    assert error.value.status_code == 400


def test_rejects_non_http_scheme():
    with pytest.raises(HTTPException) as error:
        _validate_public_url("file:///etc/passwd")
    assert error.value.status_code == 400
