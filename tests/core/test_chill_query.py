import pytest
from core import chill_query


def test_chill_get_evr_builds_command_and_calls_query_process(mocker):
    mock_qp = mocker.patch('core.chill_query.query_process', return_value='evr output')

    result = chill_query.chill_get_evr(
        sessionId='123',
        evrTypes='f',
        evrNames='EVR_%',
        eventId='42',
        evrLevel='INFO',
        evrModule='MOD_%',
        timeType='ERT',
        startTime='2024-001T00:00:00.000',
        endTime='2024-002T00:00:00.000',
        timeout=30,
    )

    expected = [
        'chill_get_evrs',
        '--testKey', '123',
        '--evrTypes', 'f',
        '--namePattern', 'EVR_%',
        '--eventId', '42',
        '--level', 'INFO',
        '--modulePattern', 'MOD_%',
        '--timeType', 'ERT',
        '--beginTime', '2024-001T00:00:00.000',
        '--endTime', '2024-002T00:00:00.000',
    ]
    mock_qp.assert_called_once_with(expected, 30)
    assert result == 'evr output'


def test_chill_get_evr_minimal(mocker):
    mock_qp = mocker.patch('core.chill_query.query_process', return_value='ok')
    result = chill_query.chill_get_evr(sessionId='123', timeout=None)
    mock_qp.assert_called_once_with(['chill_get_evrs', '--testKey', '123'], None)
    assert result == 'ok'


def test_chill_get_eha_builds_command_and_calls_query_process(mocker):
    mock_qp = mocker.patch('core.chill_query.query_process', return_value='eha output')

    result = chill_query.chill_get_eha(
        sessionId='456',
        channelTypes='fs',
        channelIds='CHAN1,CHAN2',
        inAlarmFilter='RED',
        timeType='SCET',
        startTime='2024-01-01T00:00:00',
        endTime='2024-01-02T00:00:00',
        timeout=45,
    )

    expected = [
        'chill_get_chanvals',
        '--testKey', '456',
        '--channelTypes', 'fs',
        '--channelIds', 'CHAN1,CHAN2',
        '--alarmOnly', 'RED',
        '--timeType', 'SCET',
        '--beginTime', '2024-01-01T00:00:00',
        '--endTime', '2024-01-02T00:00:00',
    ]
    mock_qp.assert_called_once_with(expected, timeout=45)
    assert result == 'eha output'


def test_chill_get_eha_minimal(mocker):
    mock_qp = mocker.patch('core.chill_query.query_process', return_value='ok')
    result = chill_query.chill_get_eha(sessionId='456')
    mock_qp.assert_called_once_with(['chill_get_chanvals', '--testKey', '456'], timeout=None)
    assert result == 'ok'


def test_chill_get_dp_builds_command_and_calls_query_process(mocker):
    mock_qp = mocker.patch('core.chill_query.query_process', return_value='dp output')

    result = chill_query.chill_get_dp(
        sessionId='789',
        dpStatus='--completeOnly',
        apIds='1,2,3',
        timeType='SCLK',
        startTime='sclk1',
        endTime='sclk2',
        timeout=20,
    )

    expected = [
        'chill_get_products',
        '--testKey', '789',
        '--completeOnly',
        '--productApid', '1,2,3',
        '--timeType', 'SCLK',
        '--beginTime', 'sclk1',
        '--endTime', 'sclk2',
    ]
    mock_qp.assert_called_once_with(expected, timeout=20)
    assert result == 'dp output'


def test_chill_get_dp_ignores_empty_dp_status(mocker):
    mock_qp = mocker.patch('core.chill_query.query_process', return_value='ok')
    result = chill_query.chill_get_dp(sessionId='789', dpStatus='', apIds='5')
    mock_qp.assert_called_once_with(
        ['chill_get_products', '--testKey', '789', '--productApid', '5'],
        timeout=None,
    )
    assert result == 'ok'
