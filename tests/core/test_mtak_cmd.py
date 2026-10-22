import pytest
import core.mtak_cmd as mtak_cmd


@pytest.fixture(autouse=True)
def mock_mtak_worker(mocker):
    """Replace the module-level worker with a mock so no real MTAK starts."""
    mocker.patch.object(mtak_cmd, 'mtak_worker')


def test_mtak_startup_timeout_success():
    mtak_cmd.mtak_worker.wait_for_completion.return_value = (True, None)

    result = mtak_cmd.mtak_startup_timeout([1, 2], 'AB', 30)

    mtak_cmd.mtak_worker.submit_func.assert_called_once_with(
        mtak_cmd.mtak_startup_timeout_,
        sessionIds=[1, 2],
        defaultCmdString='AB',
    )
    mtak_cmd.mtak_worker.wait_for_completion.assert_called_once_with(30)
    assert result is True


def test_mtak_startup_timeout_raises_on_error():
    mtak_cmd.mtak_worker.wait_for_completion.return_value = (None, 'startup failed')

    with pytest.raises(Exception, match='startup failed'):
        mtak_cmd.mtak_startup_timeout([1], 'A', 30)


def test_mtak_shutdown():
    mtak_cmd.mtak_shutdown()
    mtak_cmd.mtak_worker.reset.assert_called_once()


def test_mtak_send_fsw_cmd_success():
    mtak_cmd.mtak_worker.wait_for_completion.return_value = ('fsw sent', None)

    result = mtak_cmd.mtak_send_fsw_cmd(1, 'FSW_CMD 1', 'A', True, 15)

    mtak_cmd.mtak_worker.submit_func.assert_called_once_with(
        mtak_cmd.mtak_send_fsw_cmd_,
        sessionId=1,
        cmdString='FSW_CMD 1',
        stringSelection='A',
        validate=True,
    )
    mtak_cmd.mtak_worker.wait_for_completion.assert_called_once_with(15)
    assert result == 'fsw sent'


def test_mtak_send_fsw_cmd_raises_on_message():
    mtak_cmd.mtak_worker.wait_for_completion.return_value = (False, 'fsw error')

    with pytest.raises(Exception, match='fsw error'):
        mtak_cmd.mtak_send_fsw_cmd(1, 'FSW_CMD', 'A', True, 15)


def test_mtak_send_hw_cmd_success():
    mtak_cmd.mtak_worker.wait_for_completion.return_value = ('hw sent', None)

    result = mtak_cmd.mtak_send_hw_cmd(2, 'HW_STEM', 'B', 10)

    mtak_cmd.mtak_worker.submit_func.assert_called_once_with(
        mtak_cmd.mtak_send_hw_cmd_,
        sessionId=2,
        cmdStem='HW_STEM',
        stringSelection='B',
    )
    mtak_cmd.mtak_worker.wait_for_completion.assert_called_once_with(10)
    assert result == 'hw sent'


def test_mtak_send_sse_cmd_success():
    mtak_cmd.mtak_worker.wait_for_completion.return_value = ('sse sent', None)

    result = mtak_cmd.mtak_send_sse_cmd(3, 'SSE_CMD', 20)

    mtak_cmd.mtak_worker.submit_func.assert_called_once_with(
        mtak_cmd.mtak_send_sse_cmd_,
        sessionId=3,
        cmdString='SSE_CMD',
    )
    mtak_cmd.mtak_worker.wait_for_completion.assert_called_once_with(20)
    assert result == 'sse sent'


def test_mtak_send_fsw_file_success():
    mtak_cmd.mtak_worker.wait_for_completion.return_value = ('file sent', None)

    result = mtak_cmd.mtak_send_fsw_file(4, '/src/file', '/dest/file', 2, True, 'AB', 25)

    mtak_cmd.mtak_worker.submit_func.assert_called_once_with(
        mtak_cmd.mtak_send_fsw_file_,
        sessionId=4,
        sourcePath='/src/file',
        targetLoc='/dest/file',
        fileType=2,
        overwrite=True,
        stringSelection='AB',
    )
    mtak_cmd.mtak_worker.wait_for_completion.assert_called_once_with(25)
    assert result == 'file sent'


def test_mtak_send_scmf_file_success():
    mtak_cmd.mtak_worker.wait_for_completion.return_value = ('scmf sent', None)

    result = mtak_cmd.mtak_send_scmf_file(5, '/path/to/scmf', True, 30)

    mtak_cmd.mtak_worker.submit_func.assert_called_once_with(
        mtak_cmd.mtak_send_fsw_scmf_,
        sessionId=5,
        filePath='/path/to/scmf',
        disableChecks=True,
    )
    mtak_cmd.mtak_worker.wait_for_completion.assert_called_once_with(30)
    assert result == 'scmf sent'
