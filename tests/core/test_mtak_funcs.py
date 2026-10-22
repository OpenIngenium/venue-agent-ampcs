import pytest
from core import mtak_funcs


def _configure_file_read_backwards(mocker, lines):
    """Helper to make FileReadBackwards yield `lines` in reverse-read order."""
    mock_cls = mocker.patch('core.mtak_funcs.FileReadBackwards')
    frb = mock_cls.return_value.__enter__.return_value
    frb.readline.side_effect = list(reversed(lines)) + ['']
    return mock_cls


def test_get_last_lines_reads_and_reverses(mocker):
    _configure_file_read_backwards(mocker, ['first', 'second', 'third'])
    result = mtak_funcs.get_last_lines('/some/log', 3)
    assert result == ['first', 'second', 'third']


def test_get_last_lines_respects_num_lines(mocker):
    _configure_file_read_backwards(mocker, ['first', 'second', 'third'])
    result = mtak_funcs.get_last_lines('/some/log', 2)
    assert result == ['second', 'third']


def test_get_last_lines_truncates_long_lines(mocker):
    long_line = 'x' * 1025
    _configure_file_read_backwards(mocker, ['short', long_line])
    result = mtak_funcs.get_last_lines('/some/log', 2)
    assert result == ['short', 'x' * 1024]


def test_get_last_error_from_logs_finds_error(mocker):
    mocker.patch('core.mtak_funcs.get_last_lines', return_value=['INFO line', 'ERROR boom', 'FATAL argh'])
    assert mtak_funcs.get_last_error_from_logs('/log') == 'FATAL argh'


def test_get_last_error_from_logs_returns_empty_when_no_error(mocker):
    mocker.patch('core.mtak_funcs.get_last_lines', return_value=['INFO line', 'DEBUG line'])
    assert mtak_funcs.get_last_error_from_logs('/log') == ''


def test_get_mtak_error_appends_log_error(mocker):
    mocker.patch('core.mtak_funcs.get_last_error_from_logs', return_value='log-error-line')
    result = mtak_funcs.get_mtak_error('main error', '/path/to/log')
    assert 'main error' in result
    assert 'Error from MTAK log (/path/to/log: log-error-line)' in result


def test_get_mtak_error_returns_error_unchanged_when_no_log_line(mocker):
    mocker.patch('core.mtak_funcs.get_last_error_from_logs', return_value='')
    assert mtak_funcs.get_mtak_error('main error', '/path/to/log') == 'main error'


def test_get_mtak_error_returns_error_unchanged_when_no_log_path():
    assert mtak_funcs.get_mtak_error('main error', None) == 'main error'


def test_mtak_startup_timeout_success(mocker):
    mock_startup = mocker.patch('core.mtak_funcs.mtk.startup', return_value=None)
    mocker.patch('core.mtak_funcs.mtk._logFile', '/tmp/mtak.log', create=True)
    result = mtak_funcs.mtak_startup_timeout_([1, 2], 'AB')
    mock_startup.assert_called_once_with(
        sessionKeys=[1, 2],
        defaultStringId='AB',
        receiveEha=False,
        receiveEvrs=False,
        receiveProducts=False,
        receiveSse=False,
        receiveFsw=False,
        enableFileLog=True,
        throwOnError=True,
    )
    assert result == (True, None)


def test_mtak_startup_timeout_failure(mocker):
    mocker.patch('core.mtak_funcs.mtk.startup', side_effect=Exception('startup failed'))
    mocker.patch('core.mtak_funcs.mtk._logFile', '/tmp/mtak.log', create=True)
    mocker.patch('core.mtak_funcs.get_last_error_from_logs', return_value='log error')
    result = mtak_funcs.mtak_startup_timeout_([1], 'A')
    assert result[0] is False
    assert 'Error in mtak_startup_timeout_' in result[1]
    assert 'log error' in result[1]


def test_mtak_send_fsw_cmd_success(mocker):
    mock_send = mocker.patch('core.mtak_funcs.mtk.send_fsw_cmd', return_value='fsw sent')
    mocker.patch('core.mtak_funcs.mtk._logFile', '/tmp/mtak.log', create=True)
    result = mtak_funcs.mtak_send_fsw_cmd_(1, 'FSW_CMD 1', 'A', True)
    mock_send.assert_called_once_with(
        command='FSW_CMD 1',
        validate=True,
        stringId='A',
        throwOnError=True,
        sessionKey=1,
    )
    assert result == ('fsw sent', None)


def test_mtak_send_fsw_cmd_failure(mocker):
    mocker.patch('core.mtak_funcs.mtk.send_fsw_cmd', side_effect=Exception('fail'))
    mocker.patch('core.mtak_funcs.mtk._logFile', '/tmp/mtak.log', create=True)
    mocker.patch('core.mtak_funcs.get_last_error_from_logs', return_value='log error')
    result = mtak_funcs.mtak_send_fsw_cmd_(2, 'FSW_CMD 2', 'B', False)
    assert result[0] is False
    assert 'Error in mtak_send_fsw_cmd_' in result[1]


def test_mtak_send_hw_cmd_success(mocker):
    mock_send = mocker.patch('core.mtak_funcs.mtk.send_hw_cmd', return_value='hw sent')
    mocker.patch('core.mtak_funcs.mtk._logFile', '/tmp/mtak.log', create=True)
    result = mtak_funcs.mtak_send_hw_cmd_(1, 'HW_STEM', 'A')
    mock_send.assert_called_once_with(
        command='HW_STEM',
        throwOnError=True,
        stringId='A',
        sessionKey=1,
    )
    assert result == ('hw sent', None)


def test_mtak_send_sse_cmd_success(mocker):
    mock_send = mocker.patch('core.mtak_funcs.mtk.send_sse_cmd', return_value='sse sent')
    mocker.patch('core.mtak_funcs.mtk._logFile', '/tmp/mtak.log', create=True)
    result = mtak_funcs.mtak_send_sse_cmd_(1, 'SSE_CMD')
    mock_send.assert_called_once_with(
        command='SSE_CMD',
        throwOnError=True,
        sessionKey=1,
    )
    assert result == ('sse sent', None)


def test_mtak_send_fsw_file_success(mocker):
    mock_send = mocker.patch('core.mtak_funcs.mtk.send_fsw_file', return_value='file sent')
    mocker.patch('core.mtak_funcs.mtk._logFile', '/tmp/mtak.log', create=True)
    result = mtak_funcs.mtak_send_fsw_file_(1, '/src', '/dest', 2, True, 'AB')
    mock_send.assert_called_once_with(
        source='/src',
        target='/dest',
        type=2,
        overwrite=True,
        throwOnError=True,
        stringId='AB',
        sessionKey=1,
    )
    assert result == ('file sent', None)


def test_mtak_send_fsw_scmf_success(mocker):
    mock_send = mocker.patch('core.mtak_funcs.mtk.send_fsw_scmf', return_value='scmf sent')
    mocker.patch('core.mtak_funcs.mtk._logFile', '/tmp/mtak.log', create=True)
    result = mtak_funcs.mtak_send_fsw_scmf_(1, '/path/to/scmf', True)
    mock_send.assert_called_once_with(
        filename='/path/to/scmf',
        disableChecks=True,
        throwOnError=True,
        sessionKey=1,
    )
    assert result == ('scmf sent', None)
