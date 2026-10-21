# How to run tests

VenueServer tests use `pytest` and run entirely locally: no AMPCS/WSTS session,
MTAK installation, or Redis server is required. The `mtak` and `lad` packages are
stubbed, Redis is replaced with `fakeredis`, and a throwaway RSA key pair is
generated in memory for JWT authentication (see `tests/_jwt_env.py` and
`tests/conftest.py`).

## Set up a Python virtual environment

```
python3 -m venv ve3
source ve3/bin/activate
pip install -r requirements.txt -r tests/requirements.txt
```

## Run tests

From the repository root:

```
python -m pytest tests/
```

The same command runs in GitHub Actions on Python 3.6 - 3.10
(`.github/workflows/python-tests.yml`).
