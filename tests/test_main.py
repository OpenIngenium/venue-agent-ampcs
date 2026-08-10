"""
FastAPI integration tests for all /api/v3/* endpoints in main.py.

These tests exercise the routing, request/response schemas, JWT middleware,
and error handling.  The actual calls into MTAK/LAD/CHILL/redis are mocked at
the core.venue_core boundary.
"""

import json
import os
import pytest
from fastapi.testclient import TestClient

# The app imports MTAK and other heavy dependencies; conftest/_jwt_env set up
# the necessary stubs before this import.
import main
from main import app


# ---------------------------------------------------------------------------
# Health / auth (health is already covered, but included here for auth checks)
# ---------------------------------------------------------------------------

def test_health_no_auth(no_auth_client):
    """Health must be reachable without a token."""
    resp = no_auth_client.get("/api/v3/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("OK", "ERROR", "UNKNOWN")


def test_mtak_start_missing_auth(no_auth_client):
    """Protected endpoints require a Bearer token."""
    resp = no_auth_client.post("/api/v3/mtak/start", json={"sessionIds": [1], "timeout": 30})
    assert resp.status_code == 401


def test_mtak_start_no_scope(unauthorized_client):
    """A token without an accepted scope must be rejected."""
    resp = unauthorized_client.post("/api/v3/mtak/start", json={"sessionIds": [1], "timeout": 30})
    assert resp.status_code == 403


def test_openapi_yaml_no_auth(no_auth_client):
    """OpenAPI YAML endpoint must be reachable without auth."""
    resp = no_auth_client.get("/openapi.yaml")
    assert resp.status_code == 200
    assert "openapi" in resp.text or "paths" in resp.text


def test_docs_no_auth(no_auth_client):
    """Swagger docs must be reachable without auth."""
    resp = no_auth_client.get("/docs")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# MTAK
# ---------------------------------------------------------------------------

def test_start_mtak_success(auth_client, mocker):
    """Nominal MTAK start returns session ids and a start time."""
    mocker.patch(
        "main.venue_core.core_start_mtak",
        return_value=([1, 2], "2024-001T12:00:00.000Z"),
    )
    payload = {"sessionIds": [1, 2], "timeout": 30, "defaultCmdString": "AB"}
    resp = auth_client.post("/api/v3/mtak/start", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sessionIds"] == [1, 2]
    assert "startTime" in data


def test_start_mtak_validation_error(auth_client):
    """Missing required fields in /mtak/start triggers a 400 validation error."""
    resp = auth_client.post("/api/v3/mtak/start", json={})
    assert resp.status_code == 400


def test_start_mtak_core_error(auth_client, mocker):
    """Exceptions from core_start_mtak are returned as 400 ErrorResponse."""
    mocker.patch("main.venue_core.core_start_mtak", side_effect=Exception("MTAK failed"))
    payload = {"sessionIds": [1], "timeout": 30, "defaultCmdString": "AB"}
    resp = auth_client.post("/api/v3/mtak/start", json=payload)
    assert resp.status_code == 400
    assert "MTAK failed" in resp.json()["message"]


def test_shutdown_mtak_success(auth_client, mocker):
    """Nominal MTAK shutdown returns 204."""
    mocker.patch("main.venue_core.core_stop_mtak", return_value="")
    resp = auth_client.post("/api/v3/mtak/shutdown")
    assert resp.status_code == 204


def test_shutdown_mtak_error(auth_client, mocker):
    """Exceptions from core_stop_mtak are returned as 400 ErrorResponse."""
    mocker.patch("main.venue_core.core_stop_mtak", side_effect=Exception("shutdown failed"))
    resp = auth_client.post("/api/v3/mtak/shutdown")
    assert resp.status_code == 400
    assert "shutdown failed" in resp.json()["message"]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def test_fsw_cmd_default_string(auth_client, mocker):
    """FSW command with default string selection returns cmd and time."""
    mocker.patch(
        "main.venue_core.core_send_fsw_cmd",
        return_value=("FSW_CMND arg1", "2024-001T12:00:00.000Z"),
    )
    payload = {
        "sessionId": 1,
        "commandString": "FSW_CMND arg1",
        "validate": True,
        "stringSelection": "DEFAULT",
        "timeout": 10,
    }
    resp = auth_client.post("/api/v3/cmd/fsw_cmd", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["cmdRequested"] == "FSW_CMND arg1"
    assert "dispatchTime" in data
    # core_send_fsw_cmd must have been called with stringSelection=None
    # because the route maps DEFAULT to None.
    main.venue_core.core_send_fsw_cmd.assert_called_once()
    call = main.venue_core.core_send_fsw_cmd.call_args
    print("CALL", call, type(call), call.kwargs, call.kwargs.get("stringSelection") if hasattr(call, "kwargs") else "n/a")
    assert call.kwargs.get("stringSelection") is None


def test_fsw_cmd_explicit_string(auth_client, mocker):
    """FSW command with an explicit A/B/AB string selection passes it through."""
    mocker.patch(
        "main.venue_core.core_send_fsw_cmd",
        return_value=("FSW_CMND arg1", "2024-001T12:00:00.000Z"),
    )
    payload = {
        "sessionId": 1,
        "commandString": "FSW_CMND arg1",
        "validate": False,
        "stringSelection": "A",
        "timeout": 10,
    }
    resp = auth_client.post("/api/v3/cmd/fsw_cmd", json=payload)
    assert resp.status_code == 200
    call = main.venue_core.core_send_fsw_cmd.call_args
    print("CALL", call, type(call), call.kwargs, call.kwargs.get("stringSelection") if hasattr(call, "kwargs") else "n/a")
    assert call.kwargs.get("stringSelection") == "A"


def test_fsw_cmd_error(auth_client, mocker):
    """FSW command failures surface as 400."""
    mocker.patch("main.venue_core.core_send_fsw_cmd", side_effect=Exception("no uplink"))
    payload = {
        "sessionId": 1,
        "commandString": "FSW_CMND arg1",
        "validate": True,
        "stringSelection": "DEFAULT",
        "timeout": 10,
    }
    resp = auth_client.post("/api/v3/cmd/fsw_cmd", json=payload)
    assert resp.status_code == 400


def test_hw_cmd_success(auth_client, mocker):
    """HW command returns requested stem and time."""
    mocker.patch(
        "main.venue_core.core_send_hw_cmd",
        return_value=("HW_CMND", "2024-001T12:00:00.000Z"),
    )
    payload = {
        "sessionId": 1,
        "commandStem": "HW_CMND",
        "stringSelection": "B",
        "timeout": 10,
    }
    resp = auth_client.post("/api/v3/cmd/hw_cmd", json=payload)
    assert resp.status_code == 200
    assert resp.json()["cmdRequested"] == "HW_CMND"


def test_hw_cmd_default_string(auth_client, mocker):
    """HW command with DEFAULT string selection passes None to core."""
    mocker.patch(
        "main.venue_core.core_send_hw_cmd",
        return_value=("HW_CMND", "2024-001T12:00:00.000Z"),
    )
    payload = {
        "sessionId": 1,
        "commandStem": "HW_CMND",
        "stringSelection": "DEFAULT",
        "timeout": 10,
    }
    auth_client.post("/api/v3/cmd/hw_cmd", json=payload)
    call = main.venue_core.core_send_hw_cmd.call_args
    assert call.kwargs.get("stringSelection") is None


def test_hw_cmd_error(auth_client, mocker):
    """HW command failures surface as 400."""
    mocker.patch("main.venue_core.core_send_hw_cmd", side_effect=Exception("bad stem"))
    payload = {
        "sessionId": 1,
        "commandStem": "HW_CMND",
        "stringSelection": "A",
        "timeout": 10,
    }
    resp = auth_client.post("/api/v3/cmd/hw_cmd", json=payload)
    assert resp.status_code == 400


def test_sse_cmd_success(auth_client, mocker):
    """SSE command returns requested string and time."""
    mocker.patch(
        "main.venue_core.core_send_sse_cmd",
        return_value=("SSE_CMND", "2024-001T12:00:00.000Z"),
    )
    payload = {"sessionId": 1, "commandString": "SSE_CMND", "timeout": 10}
    resp = auth_client.post("/api/v3/cmd/sse", json=payload)
    assert resp.status_code == 200
    assert resp.json()["cmdRequested"] == "SSE_CMND"


def test_sse_cmd_error(auth_client, mocker):
    mocker.patch("main.venue_core.core_send_sse_cmd", side_effect=Exception("sse fail"))
    resp = auth_client.post("/api/v3/cmd/sse", json={"sessionId": 1, "commandString": "x", "timeout": 10})
    assert resp.status_code == 400


def test_binary_file_success(auth_client, mocker):
    """Binary file dispatch returns file metadata and time."""
    mocker.patch(
        "main.venue_core.core_send_fsw_file",
        return_value=("sourcePath: /a targetLoc: /b fileType: 1 overwrite: True", "2024-001T12:00:00.000Z"),
    )
    payload = {
        "sessionId": 1,
        "sourceFilePath": "/a",
        "targetFilePath": "/b",
        "overwrite": True,
        "fileType": 1,
        "stringSelection": "AB",
        "timeout": 10,
    }
    resp = auth_client.post("/api/v3/cmd/binary_file", json=payload)
    assert resp.status_code == 200
    assert resp.json()["cmdRequested"]


def test_binary_file_error(auth_client, mocker):
    mocker.patch("main.venue_core.core_send_fsw_file", side_effect=Exception("file fail"))
    payload = {
        "sessionId": 1,
        "sourceFilePath": "/a",
        "targetFilePath": "/b",
        "overwrite": True,
        "fileType": 1,
        "stringSelection": "DEFAULT",
        "timeout": 10,
    }
    resp = auth_client.post("/api/v3/cmd/binary_file", json=payload)
    assert resp.status_code == 400


def test_scmf_file_success(auth_client, mocker):
    """SCMF file dispatch returns file metadata and time."""
    mocker.patch(
        "main.venue_core.core_send_scmf_file",
        return_value=("SCMF: /a disableChecks: False", "2024-001T12:00:00.000Z"),
    )
    payload = {"sessionId": 1, "filePath": "/a", "disableChecks": False, "timeout": 10}
    resp = auth_client.post("/api/v3/cmd/scmf", json=payload)
    assert resp.status_code == 200


def test_scmf_file_error(auth_client, mocker):
    mocker.patch("main.venue_core.core_send_scmf_file", side_effect=Exception("scmf fail"))
    resp = auth_client.post("/api/v3/cmd/scmf", json={"sessionId": 1, "filePath": "/a", "timeout": 10})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# EVR
# ---------------------------------------------------------------------------

def _get_request(client, path, json_payload):
    """FastAPI GET endpoints accept a request body; httpx get() does not support json."""
    return client.request("GET", path, json=json_payload)


def test_evr_realtime_success(auth_client, mocker):
    mocker.patch("main.venue_core.get_rt_evr", return_value=[{"evrName": "EVR1"}])
    payload = {
        "sessionId": 1,
        "evrName": "*",
        "startTime": "2024-001T00:00:00",
        "endTime": "2024-001T01:00:00",
        "timeout": 240,
    }
    resp = _get_request(auth_client, "/api/v3/evr/realtime", payload)
    assert resp.status_code == 200
    assert resp.json() == [{"evrName": "EVR1"}]


def test_evr_realtime_multi_success(auth_client, mocker):
    mocker.patch("main.venue_core.get_rt_evr_multi", return_value=[{"evrName": "EVR1"}, {"evrName": "EVR2"}])
    payload = {
        "sessionId": 1,
        "evrNames": ["EVR1", "EVR2"],
        "eventIds": [],
        "evrLevels": [],
        "startTime": "2024-001T00:00:00",
        "endTime": "2024-001T01:00:00",
        "timeout": 240,
    }
    resp = _get_request(auth_client, "/api/v3/evr/realtime_multi", payload)
    assert resp.status_code == 200


def test_evr_chill_success(auth_client, mocker):
    mocker.patch("main.venue_core.get_chill_evr", return_value=[{"evrName": "EVR1"}])
    payload = {
        "sessionId": 1,
        "evrType": ["FSW_REALTIME"],
        "evrName": "*",
        "timeType": "ERT",
        "startTime": "2024-001T00:00:00",
        "endTime": "2024-001T01:00:00",
        "timeout": 240,
    }
    resp = _get_request(auth_client, "/api/v3/evr/chill", payload)
    assert resp.status_code == 200


def test_evr_chill_multi_success(auth_client, mocker):
    mocker.patch("main.venue_core.get_chill_evr_multi", return_value=[{"evrName": "EVR1"}])
    payload = {
        "sessionId": 1,
        "evrType": ["FSW_REALTIME"],
        "evrNames": ["EVR1"],
        "eventIds": [],
        "evrLevels": [],
        "evrModules": [],
        "timeType": "ERT",
        "startTime": "2024-001T00:00:00",
        "endTime": "2024-001T01:00:00",
        "timeout": 240,
    }
    resp = _get_request(auth_client, "/api/v3/evr/chill_multi", payload)
    assert resp.status_code == 200


def test_evr_error(auth_client, mocker):
    mocker.patch("main.venue_core.get_rt_evr", side_effect=Exception("no evr"))
    payload = {
        "sessionId": 1,
        "startTime": "2024-001T00:00:00",
        "endTime": "2024-001T01:00:00",
        "timeout": 240,
    }
    resp = _get_request(auth_client, "/api/v3/evr/realtime", payload)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# EHA
# ---------------------------------------------------------------------------

def test_eha_realtime_success(auth_client, mocker):
    mocker.patch("main.venue_core.get_rt_eha", return_value=[{"channelId": "EHA1"}])
    payload = {
        "sessionId": 1,
        "channelId": "EHA1",
        "timeType": "ERT",
        "startTime": "2024-001T00:00:00",
        "endTime": "2024-001T01:00:00",
        "timeout": 240,
    }
    resp = _get_request(auth_client, "/api/v3/eha/realtime", payload)
    assert resp.status_code == 200


def test_eha_realtime_multi_success(auth_client, mocker):
    mocker.patch("main.venue_core.get_rt_eha_multi", return_value=[{"channelId": "EHA1"}])
    payload = {
        "sessionId": 1,
        "channelIds": ["EHA1", "EHA2"],
        "timeType": "ERT",
        "startTime": "2024-001T00:00:00",
        "endTime": "2024-001T01:00:00",
        "timeout": 240,
    }
    resp = _get_request(auth_client, "/api/v3/eha/realtime_multi", payload)
    assert resp.status_code == 200


def test_eha_chill_success(auth_client, mocker):
    mocker.patch("main.venue_core.get_chill_eha", return_value=[{"channelId": "EHA1"}])
    payload = {
        "sessionId": 1,
        "channelIds": ["EHA1"],
        "channelTypes": ["FSW_REALTIME"],
        "timeType": "ERT",
        "startTime": "2024-001T00:00:00",
        "endTime": "2024-001T01:00:00",
        "timeout": 240,
        "inAlarm": "RED_ALARM",
    }
    resp = _get_request(auth_client, "/api/v3/eha/chill", payload)
    assert resp.status_code == 200


def test_eha_chill_multi_success(auth_client, mocker):
    mocker.patch("main.venue_core.get_chill_eha_multi", return_value=[{"channelId": "EHA1"}])
    payload = {
        "sessionId": 1,
        "channelIds": ["EHA1"],
        "channelTypes": ["FSW_REALTIME"],
        "timeType": "ERT",
        "startTime": "2024-001T00:00:00",
        "endTime": "2024-001T01:00:00",
        "timeout": 240,
        "inAlarm": "YELLOW_ALARM",
    }
    resp = _get_request(auth_client, "/api/v3/eha/chill_multi", payload)
    assert resp.status_code == 200


def test_eha_error(auth_client, mocker):
    mocker.patch("main.venue_core.get_rt_eha", side_effect=Exception("no eha"))
    payload = {
        "sessionId": 1,
        "channelId": "EHA1",
        "startTime": "2024-001T00:00:00",
        "endTime": "2024-001T01:00:00",
        "timeout": 240,
    }
    resp = _get_request(auth_client, "/api/v3/eha/realtime", payload)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Data products
# ---------------------------------------------------------------------------

def test_dp_success(auth_client, mocker):
    mocker.patch("main.venue_core.get_dp", return_value=[{"apId": 1}])
    payload = {
        "sessionId": 1,
        "dpStatus": "ALL",
        "apIds": [1],
        "timeType": "ERT",
        "startTime": "2024-001T00:00:00",
        "endTime": "2024-001T01:00:00",
        "timeout": 240,
    }
    resp = _get_request(auth_client, "/api/v3/dp", payload)
    assert resp.status_code == 200
    assert resp.json() == [{"apId": 1}]


def test_dp_error(auth_client, mocker):
    mocker.patch("main.venue_core.get_dp", side_effect=Exception("no dp"))
    payload = {
        "sessionId": 1,
        "dpStatus": "COMPLETE",
        "startTime": "2024-001T00:00:00",
        "endTime": "2024-001T01:00:00",
        "timeout": 240,
    }
    resp = _get_request(auth_client, "/api/v3/dp", payload)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Bus 1553
# ---------------------------------------------------------------------------

def test_bus1553_success(auth_client, mocker):
    mocker.patch(
        "main.venue_core.decode_1553",
        return_value=[{"variable": "V1", "data_value": "5"}],
    )
    payload = {
        "start_time": "2024-001T00:00:00",
        "end_time": "2024-001T01:00:00",
        "duration": 10,
        "time_type": "SCET",
        "variables": "V1",
    }
    resp = _get_request(auth_client, "/api/v3/bus1553", payload)
    assert resp.status_code == 200


def test_bus1553_error(auth_client, mocker):
    mocker.patch("main.venue_core.decode_1553", side_effect=Exception("no logs"))
    payload = {
        "start_time": "2024-001T00:00:00",
        "end_time": "2024-001T01:00:00",
        "time_type": "SCET",
        "variables": "V1",
    }
    resp = _get_request(auth_client, "/api/v3/bus1553", payload)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Custom script (already covered by test_custom_script.py; brief mock tests here)
# ---------------------------------------------------------------------------

def test_script_start_success(auth_client, mocker):
    mocker.patch("main.venue_core.start_custom_script", return_value={"scriptRunId": "abc-123"})
    payload = {
        "scriptName": "test",
        "scriptPath": "custom_script_for_tests/custom_script_for_tests.py",
        "scriptHash": "x" * 64,
        "inputs": {},
        "outputs": {},
    }
    resp = auth_client.post("/api/v3/custom_script/start", json=payload)
    assert resp.status_code == 200
    assert resp.json()["scriptRunId"] == "abc-123"


def test_script_status_success(auth_client, mocker):
    mocker.patch(
        "main.venue_core.get_custom_script_status",
        return_value={"custom_script_status": "PASS"},
    )
    resp = auth_client.get("/api/v3/custom_script/abc-123")
    assert resp.status_code == 200
    assert resp.json()["custom_script_status"] == "PASS"


def test_script_halt_success(auth_client, mocker):
    mocker.patch("main.venue_core.halt_custom_script", return_value="")
    resp = auth_client.post("/api/v3/custom_script/abc-123/halt")
    assert resp.status_code == 204


def test_script_files_success(auth_client, mocker, tmp_path):
    tar = tmp_path / "log.tgz"
    tar.write_bytes(b"fake tar data")
    mocker.patch("main.venue_core.get_custom_script_files", return_value=str(tar))
    resp = auth_client.get("/api/v3/custom_script/abc-123/files")
    assert resp.status_code == 200
    assert resp.content == b"fake tar data"
