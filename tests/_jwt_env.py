# tests/_jwt_env.py
#
# Prepares the process environment before the FastAPI app is imported:
# a per-run RSA key pair for JWTs, required env vars, and stubs for the
# AMPCS-only packages (mtak, lad).

import builtins
import io
import os
import pathlib
import sys
import types
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# ----------------------------------------------------------------------
# Generate a throwaway RSA key pair for this test run (kept in memory only).
# ----------------------------------------------------------------------
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

PRIVATE_PEM = _key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("utf-8")

PUBLIC_PEM = _key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("utf-8")

os.environ.setdefault("JWT_ALGORITHM", "RS256")
os.environ.setdefault("JWT_AUDIENCE", "venue_server")

# ----------------------------------------------------------------------
# Expose the script-root for the test suite.
# ----------------------------------------------------------------------
project_root = pathlib.Path(__file__).resolve().parents[1]
os.environ.setdefault("CUSTOM_SCRIPT_BASE_DIR", str(project_root / "tests"))

# ----------------------------------------------------------------------
# Stub the optional Ingenium MTAK package so the FastAPI app can be
# imported without a real AMPCS/MTAK installation. These functions are
# not exercised by the local health/custom-script tests.
# ----------------------------------------------------------------------
mtak_mod = types.ModuleType('mtak')
wrapper_mod = types.ModuleType('mtak.wrapper')
wrapper_mod.startup = lambda **kwargs: None
wrapper_mod._logFile = None
wrapper_mod.send_fsw_cmd = lambda *args, **kwargs: None
wrapper_mod.send_hw_cmd = lambda *args, **kwargs: None
wrapper_mod.send_sse_cmd = lambda *args, **kwargs: None
wrapper_mod.send_fsw_file = lambda *args, **kwargs: None
wrapper_mod.send_fsw_scmf = lambda *args, **kwargs: None
wrapper_mod.shutdown = lambda *args, **kwargs: None
mtak_mod.wrapper = wrapper_mod
sys.modules['mtak'] = mtak_mod
sys.modules['mtak.wrapper'] = wrapper_mod

# Stub the Global LAD package, which is only used by AMPCS integration paths.
lad_mod = types.ModuleType('lad')
lad_client_mod = types.ModuleType('lad.client')
lad_gdsclient_mod = types.ModuleType('lad.gdsclient')
lad_gdsclient_mod.flattenDict = lambda *args, **kwargs: []
lad_mod.client = lad_client_mod
lad_mod.gdsclient = lad_gdsclient_mod
sys.modules['lad'] = lad_mod
sys.modules['lad.client'] = lad_client_mod
sys.modules['lad.gdsclient'] = lad_gdsclient_mod

# ----------------------------------------------------------------------
# Import utils with the test public key. utils.py reads
# exec_venue_public_pem.pem at import time; serve it from memory so the
# deployment's real key file is never read or overwritten.
# ----------------------------------------------------------------------
_real_open = builtins.open


def _open_test_public_key(file, *args, **kwargs):
    if os.path.basename(str(file)) == 'exec_venue_public_pem.pem':
        return io.StringIO(PUBLIC_PEM)
    return _real_open(file, *args, **kwargs)


with mock.patch('builtins.open', _open_test_public_key):
    import utils  # noqa: E402,F401
