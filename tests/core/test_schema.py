import pytest
from pydantic import ValidationError

from core import schema


def test_MtakStartBodyModel():
    m = schema.MtakStartBodyModel(sessionIds=[1, 2])
    assert m.sessionIds == [1, 2]
    assert m.timeout == 30
    assert m.defaultCmdString == schema.DefaultCmdString.AB

    with pytest.raises(ValidationError):
        schema.MtakStartBodyModel(sessionIds=[1], timeout=20)


def test_FswCmdBodyModel():
    m = schema.FswCmdBodyModel(sessionId=1, commandString="FSW_CMD")
    assert m.sessionId == 1
    assert m.commandString == "FSW_CMD"
    assert m.validate_ is True
    assert m.stringSelection == schema.StringSelection.DEFAULT
    assert m.timeout == 10

    with pytest.raises(ValidationError):
        schema.FswCmdBodyModel(sessionId=1, commandString="X", timeout=-1)


def test_HwCmdBodyModel():
    m = schema.HwCmdBodyModel(sessionId=1, commandStem="HW")
    assert m.sessionId == 1
    assert m.commandStem == "HW"
    assert m.stringSelection == schema.StringSelection.DEFAULT
    assert m.timeout == 10

    with pytest.raises(ValidationError):
        schema.HwCmdBodyModel(sessionId=1, commandStem="HW", timeout=-5)


def test_SseCmdBodyModel():
    m = schema.SseCmdBodyModel(sessionId=1, commandString="SSE")
    assert m.sessionId == 1
    assert m.commandString == "SSE"
    assert m.timeout == 10

    with pytest.raises(ValidationError):
        schema.SseCmdBodyModel(sessionId=1, commandString="X", timeout=-1)


def test_BinaryFileBodyModel():
    m = schema.BinaryFileBodyModel(
        sessionId=1,
        sourceFilePath="/src/file",
        targetFilePath="/dst/file",
        fileType=1,
    )
    assert m.sessionId == 1
    assert m.overwrite is True
    assert m.stringSelection == schema.StringSelection.DEFAULT
    assert m.timeout == 10

    with pytest.raises(ValidationError):
        schema.BinaryFileBodyModel(
            sessionId=1,
            sourceFilePath="/src",
            targetFilePath="/dst",
            fileType=1,
            timeout=-1,
        )


def test_ScmfFileBodyModel():
    m = schema.ScmfFileBodyModel(sessionId=1, filePath="/path/file.scmf")
    assert m.sessionId == 1
    assert m.disableChecks is False
    assert m.timeout == 10

    with pytest.raises(ValidationError):
        schema.ScmfFileBodyModel(sessionId=1, filePath="/path/file.scmf", timeout=-1)


def test_EvrRtBodyModel():
    m = schema.EvrRtBodyModel(
        sessionId=1,
        startTime="2020-001T00:00:00",
        endTime="2020-001T01:00:00",
    )
    assert m.sessionId == 1
    assert m.evrName is None
    assert m.timeout == 240

    with pytest.raises(ValidationError):
        schema.EvrRtBodyModel(sessionId=1)


def test_EvrRtMultiBodyModel():
    m = schema.EvrRtMultiBodyModel(
        sessionId=1,
        startTime="2020-001T00:00:00",
        endTime="2020-001T01:00:00",
    )
    assert m.evrNames == []
    assert m.evrLevels == []
    assert m.timeout == 240

    with pytest.raises(ValidationError):
        schema.EvrRtMultiBodyModel(sessionId=1, endTime="2020-001T01:00:00")


def test_EvrChillBodyModel():
    m = schema.EvrChillBodyModel(sessionId=1)
    assert m.evrType == []
    assert m.evrName is None
    assert m.timeType == schema.TimeType.ERT
    assert m.timeout == 240

    with pytest.raises(ValidationError):
        schema.EvrChillBodyModel()


def test_EvrChillMultiBodyModel():
    m = schema.EvrChillMultiBodyModel(sessionId=1)
    assert m.evrNames == []
    assert m.evrLevels == []
    assert m.timeout == 240

    with pytest.raises(ValidationError):
        schema.EvrChillMultiBodyModel()


def test_EhaRtBodyModel():
    m = schema.EhaRtBodyModel(
        sessionId=1,
        channelId="CHAN_1",
        startTime="2020-001T00:00:00",
        endTime="2020-001T01:00:00",
    )
    assert m.sessionId == 1
    assert m.channelId == "CHAN_1"
    assert m.timeout == 240

    with pytest.raises(ValidationError):
        schema.EhaRtBodyModel(
            sessionId=1,
            channelId="CHAN_1",
            startTime="2020-001T00:00:00",
        )


def test_EhaRtMultiBodyModel():
    m = schema.EhaRtMultiBodyModel(
        sessionId=1,
        channelIds=["CHAN_1", "CHAN_2"],
        startTime="2020-001T00:00:00",
        endTime="2020-001T01:00:00",
    )
    assert m.channelIds == ["CHAN_1", "CHAN_2"]
    assert m.timeout == 240

    with pytest.raises(ValidationError):
        schema.EhaRtMultiBodyModel(
            sessionId=1,
            startTime="2020-001T00:00:00",
            endTime="2020-001T01:00:00",
        )


def test_EhaChillBodyModel():
    m = schema.EhaChillBodyModel(sessionId=1)
    assert m.channelIds == []
    assert m.channelTypes == []
    assert m.timeType == schema.TimeType.ERT
    assert m.timeout == 240
    assert m.inAlarm is None

    with pytest.raises(ValidationError):
        schema.EhaChillBodyModel()


def test_EhaChillMultiBodyModel():
    m = schema.EhaChillMultiBodyModel(sessionId=1)
    assert m.channelIds == []
    assert m.channelTypes == []
    assert m.timeout == 240

    with pytest.raises(ValidationError):
        schema.EhaChillMultiBodyModel()


def test_DpBodyModel():
    m = schema.DpBodyModel(sessionId=1)
    assert m.dpStatus == schema.Dpstatus.ALL
    assert m.apIds == []
    assert m.timeType == schema.TimeType.ERT
    assert m.startTime is None
    assert m.endTime is None
    assert m.timeout == 240

    with pytest.raises(ValidationError):
        schema.DpBodyModel()


def test_Parse1553BodyModel():
    m = schema.Parse1553BodyModel(variables="VAR_1")
    assert m.variables == "VAR_1"
    assert m.time_type == schema.TimeType1553.SCET
    assert m.start_time is None
    assert m.end_time is None
    assert m.duration is None

    with pytest.raises(ValidationError):
        schema.Parse1553BodyModel()


def test_ScriptStartBodyModel():
    m = schema.ScriptStartBodyModel(
        scriptName="my_script",
        scriptPath="scripts/run.py",
        scriptHash="abc123",
    )
    assert m.scriptName == "my_script"
    assert m.scriptPath == "scripts/run.py"
    assert m.inputs == {}
    assert m.outputs == {}

    with pytest.raises(ValidationError):
        schema.ScriptStartBodyModel(
            scriptName="bad",
            scriptPath="/absolute/path.py",
            scriptHash="abc",
        )

    with pytest.raises(ValidationError):
        schema.ScriptStartBodyModel(
            scriptName="bad",
            scriptPath="../escape.py",
            scriptHash="abc",
        )

    with pytest.raises(ValidationError):
        schema.ScriptStartBodyModel(
            scriptName="bad",
            scriptPath="~/home.py",
            scriptHash="abc",
        )


def test_ScriptStatusResp():
    m = schema.ScriptStatusResp()
    assert m.logfile_url == ""
    assert m.logfile_path == ""
    assert m.custom_script_status == schema.CustomScriptStatus.PENDING
    assert m.logfile_lines == []
