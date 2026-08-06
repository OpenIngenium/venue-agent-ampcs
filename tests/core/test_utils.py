import jwt
import pytest

import utils


def test_get_decoded_token_valid(jwt_token):
    decoded = utils.get_decoded_token(f"Bearer {jwt_token}")
    assert decoded["sub"] == "test_user"
    assert decoded["iss"] == "test_suite"
    assert any(s.get("scope") == "execute:testbed" for s in decoded["scopes"])


def test_get_decoded_token_missing():
    with pytest.raises(Exception):
        utils.get_decoded_token(None)


def test_get_decoded_token_wrong_prefix(jwt_token):
    with pytest.raises(Exception) as exc:
        utils.get_decoded_token(f"Basic {jwt_token}")
    assert "Bearer" in str(exc.value)


def test_get_decoded_token_no_bearer_prefix(jwt_token):
    with pytest.raises(Exception):
        utils.get_decoded_token(jwt_token)


def test_get_decoded_token_expired(expired_jwt):
    with pytest.raises(Exception):
        utils.get_decoded_token(f"Bearer {expired_jwt}")


def test_has_permission_true(jwt_token):
    decoded = utils.get_decoded_token(f"Bearer {jwt_token}")
    assert utils.has_permission(decoded) is True


def test_has_permission_empty_scope(unauthorized_jwt):
    decoded = utils.get_decoded_token(f"Bearer {unauthorized_jwt}")
    assert utils.has_permission(decoded) is False


def test_has_permission_string_scopes():
    assert utils.has_permission({"scopes": ["execute:wsts"]}) is True
    assert utils.has_permission({"scopes": ["execute:other"]}) is True
    assert utils.has_permission({"scopes": ["denied:scope"]}) is False


def test_has_permission_missing_or_empty_scopes():
    assert utils.has_permission({"scopes": []}) is False
    assert utils.has_permission({}) is False
