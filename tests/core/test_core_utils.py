import datetime as _dt
import sys

import pytest

from core import core_utils


class _FakeDateTime:
    """Minimal stand-in for datetime.datetime for monkeypatching time."""
    _fixed = _dt.datetime(2021, 1, 5, 12, 0, 0, 123456)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return _dt.datetime.now()
        return cls._fixed.replace(tzinfo=tz)

    @classmethod
    def utcnow(cls):
        return cls._fixed

    @classmethod
    def strftime(cls, dt, fmt):
        return dt.strftime(fmt)

    @classmethod
    def strptime(cls, s, fmt):
        return _dt.datetime.strptime(s, fmt)


@pytest.fixture
def patch_datetime(monkeypatch):
    monkeypatch.setattr(core_utils, "datetime", _FakeDateTime)


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def test_get_utc(patch_datetime):
    result = core_utils.get_utc()
    assert result == _FakeDateTime._fixed.replace(tzinfo=_dt.timezone.utc)
    assert result.tzinfo is _dt.timezone.utc


def test_get_utc_iso(patch_datetime):
    result = core_utils.get_utc_iso()
    expected = _FakeDateTime._fixed.replace(tzinfo=_dt.timezone.utc).isoformat()
    assert result == expected


def test_get_now_isoZ(patch_datetime):
    result = core_utils.get_now_isoZ()
    assert result == "2021-01-05T12:00:00.123Z"


def test_utc_now_doy(patch_datetime):
    result = core_utils.utc_now_doy()
    assert result == "2021-005T12:00:00.123456"


def test_doyToIsoZ(patch_datetime):
    doy = "2021-005T12:00:00.123456"
    result = core_utils.doyToIsoZ(doy)
    assert result == "2021-01-05T12:00:00.123Z"


def test_normalize_with_microsecs():
    assert core_utils.normalize_with_microsecs(
        "2021-01-05T12:00:00.123456"
    ) == "2021-01-05T12:00:00.123456"
    assert core_utils.normalize_with_microsecs(
        "2021-01-05T12:00:00.123456789"
    ) == "2021-01-05T12:00:00.123456"
    assert core_utils.normalize_with_microsecs(
        "2021-01-05T12:00:00"
    ) == "2021-01-05T12:00:00.000000"


def test_iso_to_datetime():
    dt = core_utils.iso_to_datetime("2021-01-05T12:00:00.123456Z")
    assert dt == _dt.datetime(2021, 1, 5, 12, 0, 0, 123456)
    dt = core_utils.iso_to_datetime("2021-01-05T12:00:00Z")
    assert dt == _dt.datetime(2021, 1, 5, 12, 0, 0)
    dt = core_utils.iso_to_datetime("2021-01-05T12:00:00.123456")
    assert dt == _dt.datetime(2021, 1, 5, 12, 0, 0, 123456)
    with pytest.raises(ValueError):
        core_utils.iso_to_datetime("2021-01-05T12:00:00", must_have_Z=True)


def test_doy_to_datetime():
    dt = core_utils.doy_to_datetime("2021-005T12:00:00.123456")
    assert dt == _dt.datetime(2021, 1, 5, 12, 0, 0, 123456)
    dt = core_utils.doy_to_datetime("2021-005T12:00:00")
    assert dt == _dt.datetime(2021, 1, 5, 12, 0, 0)


def test_str_to_datetime():
    dt = core_utils.str_to_datetime("2021-01-05T12:00:00Z")
    assert dt == _dt.datetime(2021, 1, 5, 12, 0, 0)
    dt = core_utils.str_to_datetime("2021-005T12:00:00.123456")
    assert dt == _dt.datetime(2021, 1, 5, 12, 0, 0, 123456)
    with pytest.raises(ValueError):
        core_utils.str_to_datetime("not-a-time")


def test_validate_time():
    ttype, parsed = core_utils.validate_time("2021-005T12:00:00.123456")
    assert ttype == "SCET"
    assert parsed == _dt.datetime(2021, 1, 5, 12, 0, 0, 123456)
    ttype, parsed = core_utils.validate_time("2021-01-05T12:00:00")
    assert ttype == "SCET"
    assert parsed == _dt.datetime(2021, 1, 5, 12, 0, 0)
    ttype, parsed = core_utils.validate_time("123456.789")
    assert ttype == "SCLK"
    assert parsed == 123456.789
    with pytest.raises(core_utils.TimeParsingError):
        core_utils.validate_time("bad-time")


def test_return_validated_start_end_times():
    start, end = core_utils.return_validated_start_end_times(
        "2021-005T12:00:00", None, "SCET", 60
    )
    assert start == _dt.datetime(2021, 1, 5, 12, 0, 0)
    assert end == _dt.datetime(2021, 1, 5, 12, 1, 0)

    start, end = core_utils.return_validated_start_end_times(
        None, "2021-005T12:01:00", "SCET", 60
    )
    assert start == _dt.datetime(2021, 1, 5, 12, 0, 0)
    assert end == _dt.datetime(2021, 1, 5, 12, 1, 0)

    with pytest.raises(core_utils.TimeParsingError):
        core_utils.return_validated_start_end_times(
            "2021-005T12:00:00", "2021-005T12:01:00", "SCET", 60
        )

    with pytest.raises(core_utils.TimeParsingError):
        core_utils.return_validated_start_end_times(
            "bad-time", None, "SCET", 60
        )


def test_get_sclkscet_times(patch_datetime):
    start, end = core_utils.get_sclkscet_times()
    assert start == "2021-005T11:59:30"
    assert end == "2021-005T12:00:00"


def test_datetime_to_doy():
    dt = _dt.datetime(2021, 1, 5, 12, 0, 0, 123456)
    assert core_utils.datetime_to_doy(dt) == "2021-005T12:00:00"
    assert core_utils.datetime_to_doy(dt, res="millis") == "2021-005T12:00:00.123"
    assert core_utils.datetime_to_doy(dt, res="micros") == "2021-005T12:00:00.123456"


def test_datetime_to_isoZ():
    dt = _dt.datetime(2021, 1, 5, 12, 0, 0, 123456)
    assert core_utils.datetime_to_isoZ(dt) == "2021-01-05T12:00:00"
    assert core_utils.datetime_to_isoZ(dt, res="millis") == "2021-01-05T12:00:00.123"
    assert core_utils.datetime_to_isoZ(dt, res="micros") == "2021-01-05T12:00:00.123456"


def test_ints_to_doy():
    assert core_utils.ints_to_doy([1, 10, 100]) == ["001", "010", "100"]
    assert core_utils.ints_to_doy([1000]) == ["1000"]


def test_doys_for_lookback(patch_datetime):
    result = core_utils.doys_for_lookback(2)
    assert result == {"2021": ["003", "004", "005"]}

    # Year boundary: 2021-01-02 is DOY 002; lookback 5 days
    _FakeDateTime._fixed = _dt.datetime(2021, 1, 2, 12, 0, 0)
    result = core_utils.doys_for_lookback(5)
    assert result == {"2020": ["363", "364", "365"], "2021": ["001", "002"]}
    _FakeDateTime._fixed = _dt.datetime(2021, 1, 5, 12, 0, 0, 123456)


# ---------------------------------------------------------------------------
# PathConverter
# ---------------------------------------------------------------------------

def test_path_converter_get_schema_resolved_paths():
    dt = _dt.datetime(2021, 1, 5, 12, 0, 0)
    pc = core_utils.PathConverter(
        "/data/$USER/$DOY/$SIDE",
        start_time=dt,
        end_time=dt,
        side="A",
        username="bob",
    )
    paths = pc.get_schema_resolved_paths()
    assert "/data/bob/004/A" in paths
    assert "/data/bob/005/A" in paths


def test_path_converter_resolve_methods():
    pc = core_utils.PathConverter("/logs/$CHILL_SESS_NAME/$SIDE")
    pc._single_arg_vars["$CHILL_SESS_NAME"] = "session-1"
    pc._single_arg_vars["$SIDE"] = "A"
    single = pc._resolve_single_arg_vars()
    assert single == "/logs/session-1/A"

    pc2 = core_utils.PathConverter("/logs/$YYYY/$DOY")
    pc2._multi_arg_vars["$YYYY"] = ["2021"]
    pc2._multi_arg_vars["$DOY"] = ["004", "005"]
    paths = pc2._resolve_multi_arg_vars("/logs/$YYYY/$DOY")
    assert "/logs/2021/004" in paths
    assert "/logs/2021/005" in paths


def test_path_converter_get_date_from_logfile_path():
    pc = core_utils.PathConverter("", start_time=None, end_time=None)
    dt = pc.get_date_from_logfile_path("/logs/psyche_20210105T120000")
    assert dt == _dt.datetime(2021, 1, 5, 12, 0, 0)


def test_path_converter_determine_logfile_path_position():
    start = _dt.datetime(2021, 1, 5, 12, 0, 0)
    end = _dt.datetime(2021, 1, 5, 12, 30, 0)
    pc = core_utils.PathConverter("", start_time=start, end_time=end)
    assert pc.determine_logfile_path_position(_dt.datetime(2021, 1, 5, 11, 0, 0)) == "before"
    assert pc.determine_logfile_path_position(_dt.datetime(2021, 1, 5, 12, 10, 0)) == "within"
    assert pc.determine_logfile_path_position(_dt.datetime(2021, 1, 5, 13, 0, 0)) == "after"


def test_path_converter_filter_1553_log_files():
    start = _dt.datetime(2021, 1, 5, 12, 0, 0)
    end = _dt.datetime(2021, 1, 5, 12, 30, 0)
    pc = core_utils.PathConverter("", start_time=start, end_time=end)
    logs = [
        "/logs/psyche_20210105T110000",
        "/logs/psyche_20210105T120000",
        "/logs/psyche_20210105T130000",
    ]
    selected = pc.filter_1553_log_files(logs)
    assert "/logs/psyche_20210105T110000" in selected
    assert "/logs/psyche_20210105T120000" in selected
    assert "/logs/psyche_20210105T130000" not in selected


def test_path_converter_sort_ascending_logfile_paths():
    pc = core_utils.PathConverter("")
    paths = [
        "/logs/psyche_20210105T130000",
        "/logs/psyche_20210105T110000",
        "/logs/psyche_20210105T120000",
    ]
    sorted_paths = pc.sort_ascending_logfile_paths(paths)
    assert sorted_paths[0].endswith("110000")
    assert sorted_paths[-1].endswith("130000")


# ---------------------------------------------------------------------------
# Subprocess / file / CSV / hostname / env
# ---------------------------------------------------------------------------

def test_get_last_error_from_logs_missing(tmp_path):
    missing = tmp_path / "not-real.log"
    with pytest.raises(core_utils.InvalidFilePathError):
        core_utils.get_last_error_from_logs(str(missing), [])


def test_get_last_error_from_logs_found(tmp_path, monkeypatch):
    logfile = tmp_path / "app.log"
    logfile.write_text("INFO line\nERROR something failed\n")

    def fake_check_output(cmd, **kwargs):
        return b"INFO line\nERROR something failed\n"

    monkeypatch.setattr(core_utils.subprocess, "check_output", fake_check_output)
    result = core_utils.get_last_error_from_logs(str(logfile), [])
    assert "ERROR something failed" in result


def test_get_last_error_from_logs_not_found(tmp_path, monkeypatch):
    logfile = tmp_path / "app.log"
    logfile.write_text("INFO only\n")

    def fake_check_output(cmd, **kwargs):
        return b"INFO only\n"

    monkeypatch.setattr(core_utils.subprocess, "check_output", fake_check_output)
    result = core_utils.get_last_error_from_logs(str(logfile), [])
    assert "could not be found" in result


def test_query_process(monkeypatch):
    def fake_check_output(cmd, **kwargs):
        return b"query result"
    monkeypatch.setattr(core_utils.subprocess, "check_output", fake_check_output)
    assert core_utils.query_process(["cmd"], 10) == "query result"


def test_query_process_long_response(monkeypatch):
    long_resp = "x" * 1200

    def fake_check_output(cmd, **kwargs):
        return long_resp.encode("utf-8")
    monkeypatch.setattr(core_utils.subprocess, "check_output", fake_check_output)
    result = core_utils.query_process(["cmd"], 10)
    # query_process returns the full output; only the log is abridged.
    assert result == long_resp


def test_get_csv_row_reader():
    reader = core_utils.get_csv_row_reader("a,b\nc,d\n")
    rows = list(reader)
    assert rows == [["a", "b"], ["c", "d"]]


def test_get_hostname(monkeypatch):
    monkeypatch.setattr(core_utils.socket, "gethostname", lambda: "testhost")
    assert core_utils.get_hostname() == "testhost"


def test_get_venue_type(monkeypatch):
    monkeypatch.setenv("INGENIUM_VENUE_TYPE", "WSTS")
    assert core_utils.get_venue_type() == core_utils.VenueType.WSTS

    monkeypatch.setenv("INGENIUM_VENUE_TYPE", "atlo")
    assert core_utils.get_venue_type() == core_utils.VenueType.ATLO

    monkeypatch.setenv("INGENIUM_VENUE_TYPE", "testbed")
    assert core_utils.get_venue_type() == core_utils.VenueType.TESTBED

    monkeypatch.setenv("INGENIUM_VENUE_TYPE", "UNKNOWN")
    with pytest.raises(core_utils.VenueTypeNotFound):
        core_utils.get_venue_type()

    monkeypatch.setenv("INGENIUM_VENUE_TYPE", "")
    with pytest.raises(core_utils.VenueTypeNotFound):
        core_utils.get_venue_type()


def test_get_testbed_name(monkeypatch):
    monkeypatch.delenv("INGENIUM_TESTBED_NAME", raising=False)
    assert core_utils.get_testbed_name() is None
    monkeypatch.setenv("INGENIUM_TESTBED_NAME", "tb1")
    assert core_utils.get_testbed_name() == "tb1"
    monkeypatch.setenv("INGENIUM_TESTBED_NAME", "   ")
    assert core_utils.get_testbed_name() is None


def test_get_sse_hostname(monkeypatch):
    monkeypatch.delenv("INGENIUM_SSE_HOSTNAME", raising=False)
    assert core_utils.get_sse_hostname() is None
    monkeypatch.setenv("INGENIUM_SSE_HOSTNAME", "ssehost")
    assert core_utils.get_sse_hostname() == "ssehost"
    monkeypatch.setenv("INGENIUM_SSE_HOSTNAME", "   ")
    assert core_utils.get_sse_hostname() is None


def test_get_env(monkeypatch):
    monkeypatch.delenv("TEST_VAR", raising=False)
    assert core_utils.get_env("TEST_VAR") is None
    monkeypatch.setenv("TEST_VAR", "  ")
    assert core_utils.get_env("TEST_VAR") is None
    monkeypatch.setenv("TEST_VAR", "hello")
    assert core_utils.get_env("TEST_VAR") == "hello"
    monkeypatch.setenv("TEST_INT", "42")
    assert core_utils.get_env("TEST_INT", cast_type=int) == 42


def test_str2bool():
    assert core_utils.str2bool(True) is True
    assert core_utils.str2bool(False) is False
    assert core_utils.str2bool("true") is True
    assert core_utils.str2bool("True") is True
    assert core_utils.str2bool("false") is False
    assert core_utils.str2bool("foo") is False


# ---------------------------------------------------------------------------
# ErrorCapturing and exceptions
# ---------------------------------------------------------------------------

def test_error_capturing():
    with core_utils.ErrorCapturing() as errs:
        sys.stderr.write("error one\n")
        print("error two", file=sys.stderr)
    assert "error one" in errs
    assert "error two" in errs


def test_exceptions():
    excs = [
        core_utils.TimeoutError,
        core_utils.InvalidFilePathError,
        core_utils.ConsolePortFileNotFound,
        core_utils.VenueTypeNotFound,
        core_utils.SocketConnectionError,
        core_utils.LogParseError,
    ]
    for exc in excs:
        with pytest.raises(exc):
            raise exc("test")

    with pytest.raises(core_utils.TimeParsingError):
        raise core_utils.TimeParsingError("bad time")
    err = core_utils.TimeParsingError("bad time")
    assert err.message == "bad time"
