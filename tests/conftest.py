import tests._jwt_env as jwt_env
import datetime
import logging
import os
from unittest.mock import patch

import fakeredis
import jwt
import pytest
from fastapi.testclient import TestClient

# ----------------------------------------------------------------------
# Import the FastAPI app **after** the environment is prepared.
# ----------------------------------------------------------------------
from main import app


@pytest.fixture(scope="function", autouse=True)
def per_test_logging(request, tmp_path):
    """
    Attach a ``FileHandler`` writing to a per-test log file on the root
    logger, and remove it when the test finishes. Yields the log file path.
    """
    safe_name = request.node.nodeid.replace("/", "_").replace("::", "__")
    safe_name = safe_name.replace("[", "_").replace("]", "_")
    log_file = tmp_path / f"{safe_name}.log"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(file_handler)

    yield log_file

    logger.removeHandler(file_handler)
    file_handler.close()


def _make_jwt(iat_offset, exp_offset, scopes):
    """Sign a JWT with the test private key; offsets are seconds from now."""
    now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    payload = {
        "sub": "test_user",
        "iat": now_ts + iat_offset,
        "exp": now_ts + exp_offset,
        "iss": "test_suite",
        "scopes": scopes,
    }
    token = jwt.encode(payload, jwt_env.PRIVATE_PEM,
                       algorithm=os.getenv("JWT_ALGORITHM", "RS256"))
    # PyJWT 2.x returns ``str``; older versions return ``bytes``.
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


@pytest.fixture(scope="session")
def jwt_token():
    """Valid JWT with an accepted scope."""
    return _make_jwt(0, 3600, [{"scope": "execute:testbed"}])


@pytest.fixture(scope="session")
def unauthorized_jwt():
    """JWT with a valid signature/expiry but no accepted scope (-> 403)."""
    return _make_jwt(0, 3600, [{}])


@pytest.fixture(scope="session")
def expired_jwt():
    """Expired JWT with an otherwise accepted scope (-> 401)."""
    return _make_jwt(-7200, -3600, [{"scope": "execute:testbed"}])


@pytest.fixture(scope="session", autouse=True)
def fake_redis():
    """Patch redis.Redis and redis.StrictRedis with a shared FakeRedis server for the entire test session."""
    server = fakeredis.FakeServer()
    def _fake(*args, **kwargs):
        kwargs.setdefault('server', server)
        return fakeredis.FakeRedis(*args, **kwargs)
    with patch("redis.Redis", _fake), patch("redis.StrictRedis", _fake):
        yield server


@pytest.fixture(scope="module")
def auth_client(jwt_token):
    """
    Returns a TestClient that runs the FastAPI app locally and includes the
    Bearer token in the `Authorization` header for every request.
    """
    with TestClient(app) as c:
        # Set default headers for the client instance.
        c.headers.update({"Authorization": f"Bearer {jwt_token}"})
        yield c


@pytest.fixture(scope="module")
def no_auth_client():
    """TestClient with no Authorization header."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def unauthorized_client(unauthorized_jwt):
    """TestClient with a valid JWT but without an accepted scope."""
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {unauthorized_jwt}"})
        yield c


@pytest.fixture(scope="module")
def expired_client(expired_jwt):
    """TestClient with an expired JWT."""
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {expired_jwt}"})
        yield c
