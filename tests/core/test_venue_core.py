import json
import os
import pytest
from unittest.mock import patch, MagicMock, mock_open

import core.mtak_cmd

# Replace the real MTAK worker with a Mock so any module that calls it uses the Mock.
core.mtak_cmd.mtak_worker = MagicMock()

import core.venue_core as venue_core


EVR_CSV = 'a,1,b,EVR,MOD,INFO,100,1,c,true,false,12345,2023-001T00:00:00,2023-001T00:00:00,d,message'

EHA_CSV = 'a,1,b,CHAN1,c,1,NAME,d,2023-001T00:00:00,2023-001T00:00:00,12345,DN,2.5,STATUS,DNAL,EUASL,false,true,FSW'

DP_CSV = 'a,1,b,1,100,TYPE,2023-001T00:00:00,2023-001T00:00:00,2023-001T00:00:00,12345,/path,10,11,12,13,14,15,16,17,123.4,19,COMPLETE'


@patch('core.venue_core.get_now_isoZ', return_value='now-iso')
@patch('core.venue_core.mtak_startup_timeout')
def test_core_start_mtak(mock_startup, mock_now):
    result = venue_core.core_start_mtak([1, 2], 'A', 30)
    mock_startup.assert_called_once_with(sessionIds=[1, 2], defaultCmdString='A', timeout_sec=30)
    assert result == ([1, 2], 'now-iso')


@patch('core.venue_core.mtak_shutdown')
def test_core_stop_mtak(mock_shutdown):
    result = venue_core.core_stop_mtak()
    mock_shutdown.assert_called_once()
    assert result == ''


@patch('core.venue_core.get_now_isoZ', return_value='now-iso')
@patch('core.venue_core.mtak_send_fsw_cmd')
def test_core_send_fsw_cmd(mock_send, mock_now):
    result = venue_core.core_send_fsw_cmd(1, 'FSW', True, 'A', 10)
    mock_send.assert_called_once_with(sessionId=1, cmdString='FSW', validate=True,
                                      stringSelection='A', timeout_sec=10)
    assert result == ('FSW', 'now-iso')


@patch('core.venue_core.get_now_isoZ', return_value='now-iso')
@patch('core.venue_core.mtak_send_hw_cmd')
def test_core_send_hw_cmd(mock_send, mock_now):
    result = venue_core.core_send_hw_cmd(1, 'HW', 'A', 10)
    mock_send.assert_called_once_with(sessionId=1, cmdStem='HW', stringSelection='A', timeout_sec=10)
    assert result == ('HW', 'now-iso')


@patch('core.venue_core.get_now_isoZ', return_value='now-iso')
@patch('core.venue_core.mtak_send_sse_cmd')
def test_core_send_sse_cmd(mock_send, mock_now):
    result = venue_core.core_send_sse_cmd(1, 'SSE', 10)
    mock_send.assert_called_once_with(sessionId=1, cmdString='SSE', timeout_sec=10)
    assert result == ('SSE', 'now-iso')


@patch('core.venue_core.get_now_isoZ', return_value='now-iso')
@patch('core.venue_core.mtak_send_fsw_file')
def test_core_send_fsw_file(mock_send, mock_now):
    result = venue_core.core_send_fsw_file(1, '/src', '/dst', 2, True, 'A', 10)
    mock_send.assert_called_once_with(sessionId=1, sourcePath='/src', targetLoc='/dst',
                                      fileType=2, overwrite=True, stringSelection='A',
                                      timeout_sec=10)
    assert result[0] == 'sourcePath: /src targetLoc: /dst fileType: 2 overwrite: True'
    assert result[1] == 'now-iso'


@patch('core.venue_core.get_now_isoZ', return_value='now-iso')
@patch('core.venue_core.mtak_send_scmf_file')
def test_core_send_scmf_file(mock_send, mock_now):
    result = venue_core.core_send_scmf_file(1, '/scmf', False, 10)
    mock_send.assert_called_once_with(sessionId=1, filePath='/scmf', disableChecks=False, timeout_sec=10)
    assert result == ('SCMF: /scmf disableChecks: False', 'now-iso')


@patch('core.venue_core.lad_query.lad_get_evr', return_value=[{
    'sessionNumber': '1', 'evrId': '100', 'vcid': '1', 'evrName': 'EVR1',
    'evrLevel': 'INFO', 'isFsw': 'true', 'message': 'hello', 'sclk': '12345',
    'ert': '2023-001T00:00:00', 'scet': '2023-001T00:00:00', 'isRealTime': 'false'
}])
def test_get_rt_evr(mock_lad):
    result = venue_core.get_rt_evr(1, 10, evrName='EVR1', timeType=venue_core.TimeType.ERT,
                                   startTime='2023-001T00:00:00', endTime='2023-001T00:01:00')
    mock_lad.assert_called_once()
    assert len(result) == 1
    assert result[0]['evrName'] == 'EVR1'
    assert result[0]['sessionId'] == 1


@patch('core.venue_core.lad_query.lad_get_evr_multi', return_value=[{
    'sessionNumber': '1', 'evrId': '100', 'vcid': '1', 'evrName': 'EVR1',
    'evrLevel': 'INFO', 'isFsw': 'true', 'message': 'hello', 'sclk': '12345',
    'ert': '2023-001T00:00:00', 'scet': '2023-001T00:00:00', 'isRealTime': 'false'
}])
def test_get_rt_evr_multi(mock_lad):
    result = venue_core.get_rt_evr_multi(1, 10, evrNames=['EVR1'], timeType=venue_core.TimeType.ERT,
                                         startTime='2023-001T00:00:00', endTime='2023-001T00:01:00')
    mock_lad.assert_called_once()
    assert len(result) == 1
    assert result[0]['evrName'] == 'EVR1'


@patch('core.venue_core.chill_query.chill_get_evr', return_value=EVR_CSV)
def test_get_chill_evr(mock_chill):
    result = venue_core.get_chill_evr(1, evrTypes=[venue_core.EVRType.FSW_REALTIME], evrName='EVR',
                                      timeType=venue_core.TimeType.ERT,
                                      startTime='2023-001T00:00:00', endTime='2023-001T00:01:00', timeout=5)
    mock_chill.assert_called_once()
    assert len(result) == 1
    assert result[0]['evrName'] == 'EVR'
    assert result[0]['sessionId'] == 1


@patch('core.venue_core.chill_query.chill_get_evr', return_value=EVR_CSV)
def test_get_chill_evr_multi(mock_chill):
    result = venue_core.get_chill_evr_multi(1, evrTypes=[venue_core.EVRType.FSW_REALTIME],
                                            evrNames=['EVR'], timeType=venue_core.TimeType.ERT,
                                            startTime='2023-001T00:00:00', endTime='2023-001T00:01:00', timeout=5)
    mock_chill.assert_called_once()
    assert len(result) == 1
    assert result[0]['evrName'] == 'EVR'


@patch('core.venue_core.lad_query.lad_get_eha', return_value=[{
    'sessionNumber': '1', 'channelId': 'CHAN1', 'dn': '10', 'eu': '2.5', 'vcid': '1',
    'channelType': 'FSW', 'status': 'OK', 'dnAlarmLevel': 'NONE', 'euAlarmLevel': 'NONE',
    'sclk': '12345', 'ert': '2023-001T00:00:00', 'scet': '2023-001T00:00:00', 'isRealTime': 'false'
}])
def test_get_rt_eha(mock_lad):
    result = venue_core.get_rt_eha(1, 10, channelId='CHAN1', timeType=venue_core.TimeType.ERT,
                                   startTime='2023-001T00:00:00', endTime='2023-001T00:01:00')
    mock_lad.assert_called_once()
    assert len(result) == 1
    assert result[0]['channelId'] == 'CHAN1'


@patch('core.venue_core.lad_query.lad_get_eha_multi', return_value=[{
    'sessionNumber': '1', 'channelId': 'CHAN1', 'dn': '10', 'eu': '2.5', 'vcid': '1',
    'channelType': 'FSW', 'status': 'OK', 'dnAlarmLevel': 'NONE', 'euAlarmLevel': 'NONE',
    'sclk': '12345', 'ert': '2023-001T00:00:00', 'scet': '2023-001T00:00:00', 'isRealTime': 'false'
}])
def test_get_rt_eha_multi(mock_lad):
    result = venue_core.get_rt_eha_multi(1, 10, channelIds=['CHAN1'], timeType=venue_core.TimeType.ERT,
                                         startTime='2023-001T00:00:00', endTime='2023-001T00:01:00')
    mock_lad.assert_called_once()
    assert len(result) == 1
    assert result[0]['channelId'] == 'CHAN1'


@patch('core.venue_core.chill_query.chill_get_eha', return_value=EHA_CSV)
def test_get_chill_eha(mock_chill):
    result = venue_core.get_chill_eha(1, channelIds=['CHAN1'], channelTypes=[venue_core.ChannelType.FSW_REALTIME],
                                      timeType=venue_core.TimeType.ERT,
                                      startTime='2023-001T00:00:00', endTime='2023-001T00:01:00', timeout=5)
    mock_chill.assert_called_once()
    assert len(result) == 1
    assert result[0]['channelId'] == 'CHAN1'


@patch('core.venue_core.chill_query.chill_get_eha', return_value=EHA_CSV)
def test_get_chill_eha_multi(mock_chill):
    result = venue_core.get_chill_eha_multi(1, channelIds=['CHAN1'], channelTypes=[venue_core.ChannelType.FSW_REALTIME],
                                            timeType=venue_core.TimeType.ERT,
                                            startTime='2023-001T00:00:00', endTime='2023-001T00:01:00', timeout=5)
    mock_chill.assert_called_once()
    assert len(result) == 1
    assert result[0]['channelId'] == 'CHAN1'


@patch('core.venue_core.chill_query.chill_get_dp', return_value=DP_CSV)
def test_get_dp(mock_chill):
    result = venue_core.get_dp(1, dpStatus=venue_core.DpStatus.COMPLETE, apIds=[100],
                               timeType=venue_core.TimeType.ERT,
                               startTime='2023-001T00:00:00', endTime='2023-001T00:01:00', timeout=5)
    mock_chill.assert_called_once()
    assert len(result) == 1
    assert result[0]['apId'] == 100


def test_load_json_with_retry(tmp_path):
    f = tmp_path / 'out.json'
    f.write_text(json.dumps({'status': 'ok'}))
    result = venue_core._load_json_with_retry(str(f))
    assert result == {'status': 'ok'}


def test_get_custom_script_status():
    import redis
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    payload = json.dumps({
        'process_id': '12345',
        'logfile_path': '/tmp/cs/123/script.log',
        'output_path': '/tmp/cs/123/output.json',
        'logfile_url': '/logs/123',
        'custom_script_temp_dir': '/tmp/cs/123'
    })
    r.set('cs-123', payload)

    with patch('core.venue_core.os.kill', side_effect=OSError('no process')) as mock_kill, \
         patch('core.venue_core._load_json_with_retry', return_value={
             'custom_script_status': 'SUCCESS',
             'inputs': {'a': 1},
             'outputs': {'b': 2}
         }) as mock_load, \
         patch('core.venue_core.get_script_log_lines', return_value=['log line']):
        result = venue_core.get_custom_script_status('cs-123')
        mock_kill.assert_called_once_with(12345, 0)
        mock_load.assert_called_once_with('/tmp/cs/123/output.json', 10, 0.1)
        assert result['custom_script_status'] == 'SUCCESS'
        assert result['logfile_lines'] == ['log line']


@patch('core.venue_core.decode_1553_log_files', return_value=[{'decoded': 'value'}])
@patch('core.venue_core.get_most_recent_1553_logfiles', return_value=['/log/1553.txt'])
@patch('core.venue_core.get_dict_path', return_value='/dict/1553.xml')
@patch('core.venue_core.return_validated_start_end_times', return_value=('2023-001T00:00:00', '2023-001T00:01:00'))
def test_decode_1553(mock_validate, get_dict, get_logs, decode):
    with patch.object(venue_core, '_irig_source', 'false'):
        result = venue_core.decode_1553('2023-001T00:00:00', '2023-001T00:01:00', 'SCET', None, 'VAR', 'user')
    assert result == [{'decoded': 'value'}]
    get_dict.assert_called_once()
    get_logs.assert_called_once()
    decode.assert_called_once()
    info, dict_path = decode.call_args[0]
    assert info['variables'] == 'VAR'
    assert info['logfile'] == ['/log/1553.txt']
    assert dict_path == venue_core._logfile_1553_dictionary_file_path
