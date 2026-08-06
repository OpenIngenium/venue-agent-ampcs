# tests/_jwt_env.py

import os
import pathlib
import sys
import tempfile
import types

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# ----------------------------------------------------------------------
# Generate a deterministic RSA key‑pair for the test run.
# ----------------------------------------------------------------------
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

_private_pem = _key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

_public_pem = _key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)

# ----------------------------------------------------------------------
# 2️ Write the public key where utils.py expects it.
# ----------------------------------------------------------------------
# utils.py lives in the project root (same dir as this repo's top‑level).  We
# construct the absolute path and drop the file there.
project_root = pathlib.Path(__file__).resolve().parents[1]   # <repo>/venue-agent
public_key_path = project_root / "exec_venue_public_pem.pem"
public_key_path.write_bytes(_public_pem)

# ----------------------------------------------------------------------
# 3️ Write the private key to a temporary file and expose its path.
# ----------------------------------------------------------------------
tmp_private = pathlib.Path(tempfile.NamedTemporaryFile(delete=False).name)
tmp_private.write_bytes(_private_pem)
os.environ["JWT_PRIVATE_KEY"] = str(tmp_private)   # used by conftest.jwt_token

os.environ.setdefault("JWT_ALGORITHM", "RS256")
os.environ.setdefault("JWT_AUDIENCE", "venue_server")

# ----------------------------------------------------------------------
# 4️ Expose the script‑root for the test suite.
# ----------------------------------------------------------------------
os.environ.setdefault("CUSTOM_SCRIPT_BASE_DIR", str(project_root)+'/tests')

# ----------------------------------------------------------------------
# 5️ Stub the optional Ingenium MTAK package so the FastAPI app can be
#    imported without a real AMPCS/MTAK installation. These functions are
#    not exercised by the local health/custom-script tests.
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