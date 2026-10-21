# Ingenium Venue Server (venue-agent-ampcs) — DeepWiki

A comprehensive guide to the repository, architecture, API, and operational procedures for the Ingenium Venue Server that interfaces with AMPCS test venues.

---

## 1. Project Overview

**Repository:** `venue-agent-ampcs`  
**License:** Apache 2.0  
**Primary Purpose:** Provide a FastAPI-based REST gateway between downstream test tools and the AMPCS ground-data system. It dispatches spacecraft commands via MTAK, queries telemetry through GlobalLAD and CHILL, decodes MIL-STD-1553 bus logs, and executes custom Python scripts on the venue host.

**Missions Supported:** Europa Clipper, Psyche  
**Venue Types:** WSTS, TESTBED, ATLO

The server is typically deployed behind NGINX on one or more ports (`19443`, `19444`, `19445`) with NGINX SSL termination on `9443`, `9444`, `9445`.

---

## 2. Technology Stack

| Category | Technology | Version/Notes |
|---|---|---|
| Web framework | FastAPI | 0.83.0 |
| ASGI server | Uvicorn | 0.16.0, host `127.0.0.1` |
| Validation | Pydantic | 1.8.2 |
| Auth | PyJWT | 2.4.0, RS256 |
| Redis client | redis | 3.5.3 |
| 1553 decoding | bitstring | 3.1.9 |
| Logging | pyaml-env | 1.2.2 for env-aware YAML |
| Process mgmt | psutil | 5.9.8 |
| Process comms | concurrent.futures.ProcessPoolExecutor | one worker for MTAK |
| AMPCS | `mtak.wrapper` (Python) | command/telemetry uplink/downlink |
| AMPCS | GlobalLAD / `lad` client | real-time telemetry |
| AMPCS | CHILL CLI (`chill_get_*`) | historical telemetry/products |
| Proxy | NGINX | SSL/TLSv1.2, HSTS |

Full dependencies are in `requirements.txt` and `tests/requirements.txt`.

---

## 3. Repository Structure

| Path | Purpose |
|---|---|
| `main.py` | FastAPI app, routers, middleware, OpenAPI, `uvicorn` bootstrap |
| `utils.py` | JWT token decoding and scope authorization |
| `core/venue_core.py` | Core business logic for all API operations |
| `core/mtak_cmd.py` | MTAK dispatch orchestration via worker |
| `core/mtak_funcs.py` | Functions executed in MTAK worker process |
| `core/worker_process.py` | `ProcessPoolExecutor` wrapper with cleanup |
| `core/chill_query.py` | Build/run `chill_get_*` command-line queries |
| `core/lad_query.py` | GlobalLAD EVR/EHA query clients |
| `core/decode_1553.py` | MIL-STD-1553 XML dictionary + log parsing |
| `core/schema.py` | Pydantic request/response models |
| `core/core_utils.py` | Time parsing, venue detection, CSV helpers |
| `core/config.py` | Timeout constants |
| `config/venueserver_dev_envs.sh` | Environment template |
| `config/gds_config/ampcs.properties` | CHILL CSV column mappings |
| `setup_venueserver.sh` | Create venv, install deps, render NGINX config |
| `start_venueserver.sh` | Source env, activate venv, run `main.py` |
| `start_nginx.sh` / `start_redis.sh` | NGINX and Redis control helpers |
| `nginx.conf.template` | Multi-instance SSL proxy template |
| `log_config.yaml` | Rotating file + console logging |
| `openapi.yaml` | Generated OpenAPI component schemas |
| `tests/` | Pytest integration and unit tests |
| `.github/workflows/python-tests.yml` | GitHub Actions CI (Python 3.6–3.10) |

---

## 4. Configuration & Environment

### Required / Primary Variables

| Variable | Purpose |
|---|---|
| `ING_VENUE_DIR` | Root of the VenueServer installation |
| `ING_MTAK_DIR` | Path to Ingenium MTAK Python package |
| `ING_LOG_DIR` | Log directory (`$USER` should be in path) |
| `CUSTOM_SCRIPT_BASE_DIR` | Root directory allowed for custom scripts |
| `CHILL_GDS` | AMPCS installation directory |
| `PATH` | Updated to include `$CHILL_GDS/bin` and `bin/tools` |
| `GDS_JAVA_OPTS` | JVM opts such as `-DGdsUserConfigDir` |

### Optional Variables

| Variable | Purpose | Default |
|---|---|---|
| `LAD_HOST` | GlobalLAD host | `HOSTNAME` |
| `LAD_PORT` | GlobalLAD port | `8887` |
| `LAD_HTTPS` | Use HTTPS for GlobalLAD | `false` |
| `BUS_1553_LOGFILE_PATH` | Glob pattern for 1553 log files (Psyche) | — |
| `LOGFILE_1553_DICTIONARY_FILE_PATH` | Path to 1553 XML dictionary (Psyche) | — |
| `IRIG_SOURCE` | Use IRIG time format for 1553 logs | `false` |
| `INGENIUM_VENUE_TYPE` | `WSTS`, `TESTBED`, or `ATLO` | — |
| `INGENIUM_TESTBED_NAME` | Optional testbed name | — |
| `INGENIUM_SSE_HOSTNAME` | Host running SSE/VxWorks | — |

### Logging

`log_config.yaml` uses `pyaml-env` to inject `ING_LOG_DIR`:

- Console handler: DEBUG → stdout
- Rotating file: 50 MB max, 20 backups, `${ING_LOG_DIR}/ing_vs.log`
- Format: `[%(asctime)s.%(msecs)03dZ] %(name)s %(levelname)s %(message)s`

---

## 5. Application Architecture

### Startup Flow

1. `main.py` imports `core.venue_core` first, then calls `restore_root_logger()` because MTAK mangles the root logger.
2. Environment variables and `sys.path` are printed for debugging.
3. `utils.print_key_info()` logs the JWT public-key CRC32.
4. `app = FastAPI()` and `app.include_router(prefix_router)` where `prefix_router = APIRouter(prefix='/api/v3')`.
5. `uvicorn.run('main:app', host='127.0.0.1', port=args.port, ...)`.

### Middleware Stack

| Middleware | Purpose |
|---|---|
| `check_jwt` | Bearer JWT validation; exempt `/docs`, `/openapi.*`, `/health` |
| `log_request` | Request-ID generation, timing, username, response-truncated logging |
| `validation_exception_handler` | Convert Pydantic validation errors to `400` (removes `422` from OpenAPI) |

### OpenAPI

- Title: **Ingenium Venue Agent AMPCS**
- Version: `15.0`
- Tags: `MTAK`, `COMMAND`, `EVR`, `EHA`, `DATA_PRODUCT`, `BUS_1553`, `SCRIPT`, `HEALTH`
- Custom `/openapi.yaml` endpoint streams generated YAML.

### Worker Model

- A single `WorkerProcess` in `core/worker_process.py` isolates MTAK and long-running custom scripts.
- `max_workers=1` prevents concurrent MTAK operations.
- `atexit.register(mtak_worker.shutdown)` cleans up child processes on exit.
- Custom scripts run in their own subprocess and use Redis to track state.

---

## 6. API Endpoint Reference

All endpoints are under `/api/v3` unless noted.

### HEALTH

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | No | Returns `HealthStatus` (`OK`/`ERROR`/`UNKNOWN`) |

### MTAK

| Method | Path | Description |
|---|---|---|
| `POST` | `/mtak/start` | Start MTAK uplink/downlink for `sessionIds`; min timeout `25s` |
| `POST` | `/mtak/shutdown` | Kill MTAK worker and child processes; returns `204` |

### COMMAND

| Method | Path | Description |
|---|---|---|
| `POST` | `/cmd/fsw_cmd` | Send flight-software command via MTAK |
| `POST` | `/cmd/hw_cmd` | Send hardware command via MTAK |
| `POST` | `/cmd/sse` | Send SSE command via MTAK |
| `POST` | `/cmd/binary_file` | Send binary file to the spacecraft |
| `POST` | `/cmd/scmf` | Send SCMF (Spacecraft Command Message File) |

### EVR

| Method | Path | Backend | Description |
|---|---|---|---|
| `GET` | `/evr/realtime` | GlobalLAD | Single or wildcard EVR query |
| `GET` | `/evr/realtime_multi` | GlobalLAD | Multiple EVR names/IDs/levels |
| `GET` | `/evr/chill` | CHILL | Historical EVR with type, time, level, module filters |
| `GET` | `/evr/chill_multi` | CHILL | Multiple historical EVRs |

### EHA

| Method | Path | Backend | Description |
|---|---|---|---|
| `GET` | `/eha/realtime` | GlobalLAD | Single EHA channel |
| `GET` | `/eha/realtime_multi` | GlobalLAD | Multiple channels |
| `GET` | `/eha/chill` | CHILL | Historical channel values |
| `GET` | `/eha/chill_multi` | CHILL | Multiple historical channels |

### DATA_PRODUCT

| Method | Path | Backend | Description |
|---|---|---|---|
| `GET` | `/dp` | CHILL | Query data products by status, APID, time |

### BUS_1553

| Method | Path | Description |
|---|---|---|
| `GET` | `/bus1553` | Decode 1553 bus logs within a time range using XML dictionary |

### SCRIPT

| Method | Path | Description |
|---|---|---|
| `POST` | `/custom_script/start` | Start a custom Python script (hash + path validated) |
| `GET` | `/custom_script/{script_run_id}` | Poll status, logs, outputs |
| `POST` | `/custom_script/{script_run_id}/halt` | Halt the running script; `204` |
| `GET` | `/custom_script/{script_run_id}/files` | Download script workspace as `tar.gz` |

### Documentation (No auth)

- `GET /docs` — Swagger UI
- `GET /openapi.json` — JSON spec
- `GET /openapi.yaml` — YAML spec

---

## 7. Request/Response Models

Key models live in `core/schema.py`.

### Enums

| Enum | Values |
|---|---|
| `DefaultCmdString` | `A`, `B`, `AB` |
| `StringSelection` | `DEFAULT`, `A`, `B`, `AB` |
| `HealthStatusEnum` | `OK`, `ERROR`, `UNKNOWN` |
| `EvrType` / `EhaType` | `FSW_REALTIME`, `FSW_RECORDED`, `SSE` |
| `AlarmType` | `RED_ALARM`, `YELLOW_ALARM`, `ANY_ALARM` |
| `TimeType` | `ERT`, `SCET`, `SCLK` |
| `TimeType1553` | `SCET`, `SCLK` |
| `CustomScriptStatus` | `PENDING`, `ERROR`, `PASS`, `FAIL` |

### Notable Request Bodies

- `MtakStartBodyModel` — `sessionIds: List[int]`, `timeout >= 25`, `defaultCmdString`
- `FswCmdBodyModel` — `sessionId`, `commandString`, `validate_` (aliased to `validate`), `stringSelection`, `timeout`
- `BinaryFileBodyModel` — `sourceFilePath` on GDS, `targetFilePath` onboard, `fileType`, `overwrite`
- `EvrChillBodyModel` — supports `evrType`, SQL-style `%` wildcards, DOY/ISO/SCLK times
- `Parse1553BodyModel` — `start_time`, `end_time`, `duration`, `time_type`, `variables`
- `ScriptStartBodyModel` — `scriptPath`, `scriptHash`, `inputs`, `outputs`

### Common Responses

- `HealthStatus` — `status`, `message`
- `ErrorResponse` — `message` (often with traceback)
- `CmdDispatchedResp` — `cmdRequested`, `dispatchTime`
- `EVRObjectResp` — full EVR fields
- `ChannelValueObjectRespModel` — channel metadata, `dn`, `eu`, alarm states, times
- `DataProductObjectRespModel` — APID, status, creation time, path, DVT, CFDP, etc.
- `Bus1553LogObject` — decoded 1553 message fields
- `ScriptRunInfo` / `ScriptStatusResp` — run ID, status, logs, outputs

---

## 8. Core Modules Deep Dive

### `core/venue_core.py`

The main orchestrator. It converts HTTP payloads to backend calls, validates times, parses CSV/JSON outputs, and manages custom-script lifecycle. Notable functions:

- `core_start_mtak()`, `core_stop_mtak()`
- `core_send_fsw_cmd()`, `core_send_hw_cmd()`, `core_send_sse_cmd()`
- `core_send_fsw_file()`, `core_send_scmf_file()`
- `get_rt_evr()`, `get_rt_evr_multi()`, `get_chill_evr()`, `get_chill_evr_multi()`
- `get_rt_eha()`, `get_rt_eha_multi()`, `get_chill_eha()`, `get_chill_eha_multi()`
- `get_dp()`
- `start_custom_script()`, `get_custom_script_status()`, `halt_custom_script()`, `get_custom_script_files()`
- `decode_1553()`

Patterns: JSON-retry loading for `output.json`; integer `sessionId` validation; Redis state keys; script-hash and path validation; zombie-process detection.

### `core/mtak_cmd.py`

Wraps MTAK calls with a `WorkerProcess`. Each call `submit_func`s the matching function in `core/mtak_funcs.py`, then `wait_for_completion(timeout_sec)` and raises on non-true output.

### `core/mtak_funcs.py`

Functions that actually call `mtak.wrapper` (`mtk.startup`, `mtk.send_fsw_cmd`, etc.). Kept in a small module to avoid `pickle` issues. They capture `SystemExit` and append the last `ERROR`/`FATAL` line from MTAK logs.

### `core/worker_process.py`

- `WorkerProcess` — process-pool executor wrapper
- `init_worker_proc()` — resets `SIGTERM`/`SIGINT` so FastAPI does not die when the worker is killed
- `shutdown()` — recursively kills worker + children, waits up to 5 s
- `reset()` — shutdown then recreate pool
- `submit_func()`, `is_running()`, `wait_for_completion()`

### `core/chill_query.py`

Builds `chill_get_evrs`, `chill_get_chanvals`, and `chill_get_products` command lines. Uses `core_utils.query_process()` to run the command with a timeout and return raw CSV output. Constants are in `core/config.py`.

### `core/lad_query.py`

GlobalLAD REST client using `lad.client` and `lad.gdsclient`.

- Config from `LAD_HOST`, `LAD_PORT`, `LAD_HTTPS`
- Default 60 s timeout
- `setMaxResults(1000)` to match GLAD setup
- `realtimeOnly()` for real-time endpoints
- Flattened response dictionary from `gdsclient.flattenDict()`

### `core/decode_1553.py`

- `XMLdictionary` — parses the 1553 XML dictionary; produces maps of variable → remote-terminal/sub-address/bit layout, enums, and polynomial coefficients.
- `BusLogMsg` — parses a single log line; extracts time, RTI, bus, status word, words, etc.
- `decode_1553_log_files()` — finds log files, filters by time and signal variables, applies dictionary, and returns decoded objects.

Supports both standard `YYYYMMDDTHHMMSS` and IRIG time (with an assumed year).

### `core/core_utils.py`

- Enums: `EVRType`, `ChannelType`, `AlarmTypeMap`, `DpStatus`, `VenueType`
- Time parsing/conversion: DOY ↔ ISO, SCLK/SCET helpers, `normalize_with_microsecs`
- `query_process()` — `subprocess.check_output` wrapper with truncated logging
- Venue/testbed/SSE hostname helpers
- `ErrorCapturing` context manager

### `core/schema.py`

All Pydantic models. Note `FswCmdBodyModel` uses `validate_` with an alias `validate` to avoid colliding with Pydantic’s built-in `validate`.

### `utils.py`

- Loads `exec_venue_public_pem.pem` and computes CRC32.
- `get_decoded_token()` — expects `Bearer <token>`, decodes RS256.
- `has_permission()` — checks for one of `execute:wsts`, `execute:sit`, `execute:testbed`, `execute:other`; supports `scope` as string or dict.

---

## 9. Data Flow Examples

### FSW Command Dispatch

```
POST /api/v3/cmd/fsw_cmd
   ↓
main.py fsw_cmd()
   ↓
core/venue_core.core_send_fsw_cmd()
   ↓
core/mtak_cmd.mtak_send_fsw_cmd()
   ↓
WorkerProcess.submit_func(core/mtak_funcs.mtak_send_fsw_cmd_)
   ↓
mtak.wrapper.send_fsw_cmd()
```

### Real-Time EVR Query

```
GET /api/v3/evr/realtime
   ↓
main.py
   ↓
core/venue_core.get_rt_evr()
   ↓
core/lad_query.lad_get_evr()
   ↓
lad.client.EvrQuery → LadClient.fetchEvrs()
   ↓
lad.gdsclient.flattenDict() → JSON list
```

### Historical EHA Query

```
GET /api/v3/eha/chill
   ↓
core/venue_core.get_chill_eha()
   ↓
core/chill_query.chill_get_eha()
   ↓
chill_get_chanvals (CLI)
   ↓
CSV → parsed rows → ChannelValueObjectRespModel list
```

### 1553 Bus Log Query

```
GET /api/v3/bus1553
   ↓
core/venue_core.decode_1553()
   ↓
core/decode_1553.decode_1553_log_files()
   ↓
XMLdictionary + glob log files + BusLogMsg filter
   ↓
List[Bus1553LogObject]
```

### Custom Script

```
POST /api/v3/custom_script/start
   ↓
validate hash + path under CUSTOM_SCRIPT_BASE_DIR
   ↓
WorkerProcess spawns script subprocess
   ↓
Redis stores {pid, paths, urls}
   ↓
GET /api/v3/custom_script/{id} reads output.json + logfile
   ↓
POST /api/v3/custom_script/{id}/halt → kill process group
   ↓
GET /api/v3/custom_script/{id}/files → tar.gz workspace
```

---

## 10. Testing

- Framework: **pytest**
- Test deps: `pytest`, `pytest-mock`, `pytest-timeout`, `pytest-cov`, `fakeredis`, `requests`
- Runs fully locally with `python -m pytest tests/` — no AMPCS/WSTS session, MTAK, or Redis needed (see `tests/README.md`).
- `tests/_jwt_env.py` stubs `mtak`/`lad` and generates an in-memory RSA key pair; the real `exec_venue_public_pem.pem` is never read or written.
- Fixtures in `tests/conftest.py` provide `fake_redis`, JWT tokens, and `TestClient` instances.
- `tests/core/` contains unit tests for each core module.
- `tests/test_main.py` uses mocked `core` functions to exercise routes.
- GitHub Actions runs Python 3.6–3.10 on Ubuntu 22.04 (`python:3.6-slim` container for 3.6).

---

## 11. Deployment & Operations

### Development

```bash
./setup_venueserver.sh -f config/venueserver_dev_envs.sh
./start_venueserver.sh -p 19443 -f config/venueserver_dev_envs.sh
# http://localhost:19443/api/v3/health
```

### Production (systemd)

1. Check out the tagged release into the venue directory.
2. Clone the Ingenium MTAK repository into `ING_MTAK_DIR`.
3. Create `venueserver_envs.sh` with all required variables.
4. Run `setup_venueserver.sh` to create `venv3` and `nginx.conf`.
5. Create NGINX service as the Ingenium user.
6. Create Redis service (version 5+).
7. Create one or more VenueServer services on ports 19443/19444/19445, each as a different Ingenium application account.

Health check:

```bash
curl https://<hostname>.jpl.nasa.gov:9443/api/v3/health
```

### Multi-Instance Mapping

| NGINX SSL Port | Upstream Port |
|---|---|
| 9443 | 19443 |
| 9444 | 19444 |
| 9445 | 19445 |

---

## 12. Security

- **Authentication:** RS256 JWT in `Authorization: Bearer <token>`.
- **Authorization:** One of `execute:wsts`, `execute:sit`, `execute:testbed`, `execute:other`.
- **Public endpoints (no JWT):** `/docs`, `/openapi.json`, `/openapi.yaml`, `*/health`.
- **Custom scripts:** Hash validation, path must be under `CUSTOM_SCRIPT_BASE_DIR`, no `..` or `~`.
- **Network:** Uvicorn binds `127.0.0.1`; NGINX terminates TLSv1.2 with HSTS and strong ciphers.

---

## 13. Notable Patterns, Limitations, and Gotchas

1. **MTAK logging side effect** — `main.py` imports `core.venue_core` before other imports and calls `restore_root_logger()` because MTAK lowers root-logger levels.
2. **Single MTAK worker** — All MTAK commands and file sends are serialized through one `WorkerProcess`.
3. **String selection** — `DEFAULT` is mapped to `None` for MTAK; `A`/`B`/`AB` are passed through.
4. **Time formats** — Multiple formats coexist (DOY `YYYY-DDDThh:mm:ss`, ISO, SCLK). `core_utils.py` normalizes and truncates to microseconds.
5. **Validation errors return 400** — Pydantic `422`s are converted to `400` and removed from the generated OpenAPI.
6. **MTAK `SystemExit`** — Caught and converted to exceptions with the last log error appended.
7. **Custom script output race** — `_load_json_with_retry()` retries up to 5 times if `output.json` is being written.
8. **1553 logs** — Currently used for Psyche; paths and dictionaries come from environment variables.
9. **Python 3.6** — Deployment venv is created with `python3.6`; CI tests 3.6–3.10.

---

## 14. Future Considerations

- Evaluate whether MTAK is still required for AMPCS >= 9.1.
- Consider moving to a newer Python version.
- Add resource limits to custom scripts.
- Standardize error codes and error-message formatting.
- Introduce async Redis and more granular permissions.
- Reduce duplication between `chill_query`/`lad_query` and the `venue_core` functions.

---

*Generated from repository review of `venue-agent-ampcs`.*
