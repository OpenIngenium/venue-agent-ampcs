import pytest
from core import lad_query
from core.schema import TimeType


def test_get_lad_https_protocol_true(monkeypatch):
    monkeypatch.setenv('LAD_HTTPS', 'True')
    assert lad_query.get_lad_https_protocol() is True


def test_get_lad_https_protocol_false(monkeypatch):
    monkeypatch.setenv('LAD_HTTPS', 'False')
    assert lad_query.get_lad_https_protocol() is False


def test_get_lad_https_protocol_empty(monkeypatch):
    monkeypatch.delenv('LAD_HTTPS', raising=False)
    assert lad_query.get_lad_https_protocol() is False


def _patch_lad_query_clients(mocker):
    mocker.patch('core.lad_query._LAD_HTTPS', False)
    mocker.patch('core.lad_query._LAD_HOST', 'ladhost')
    mocker.patch('core.lad_query._LAD_PORT', 8887)
    mocker.patch('core.lad_query.gdsclient.flattenDict', return_value=[{'mocked': 'response'}])
    return (
        mocker.patch('core.lad_query.client.LadClient', create=True),
        mocker.patch('core.lad_query.client.EvrQuery', create=True),
        mocker.patch('core.lad_query.client.ChanValQuery', create=True),
    )


def test_lad_get_evr_builds_query(mocker):
    mock_client, mock_evr_query, _ = _patch_lad_query_clients(mocker)
    evrq = mock_evr_query.return_value

    result = lad_query.lad_get_evr(
        sessionId=123,
        timeout=10,
        evrName='EVR1',
        eventId=5,
        evrLevel='INFO',
        timeType=TimeType.ERT,
        startTime='start',
        endTime='end',
    )

    evrq.setMaxResults.assert_called_once_with(1000)
    evrq.addEvrName.assert_called_once_with('EVR1')
    evrq.addEvrLevel.assert_called_once_with('INFO')
    evrq.addEventId.assert_called_once_with(5)
    evrq.useErt.assert_called_once()
    evrq.before.assert_called_once_with('end')
    evrq.addSessionNumber.assert_called_once_with(123)
    evrq.after.assert_called_once_with('start')
    evrq.realtimeOnly.assert_called_once()
    mock_client.assert_called_once_with(host='ladhost', port=8887, https=False)
    assert result == [{'mocked': 'response'}]


def test_lad_get_evr_multi_builds_query(mocker):
    mock_client, mock_evr_query, _ = _patch_lad_query_clients(mocker)
    evrq = mock_evr_query.return_value

    result = lad_query.lad_get_evr_multi(
        sessionId=42,
        timeout=15,
        evrNames=['EVR1', 'EVR2'],
        eventIds=[1, 2],
        evrLevels=['INFO', 'WARN'],
        timeType=TimeType.ERT,
        startTime='t0',
        endTime='t1',
    )

    evrq.setMaxResults.assert_called_once_with(1000)
    evrq.addSessionNumber.assert_called_once_with(42)
    evrq.addEvrName.assert_any_call('EVR1')
    evrq.addEvrName.assert_any_call('EVR2')
    evrq.addEventId.assert_any_call(1)
    evrq.addEventId.assert_any_call(2)
    evrq.addEvrLevel.assert_any_call('INFO')
    evrq.addEvrLevel.assert_any_call('WARN')
    evrq.useErt.assert_called_once()
    evrq.before.assert_called_once_with('t1')
    evrq.after.assert_called_once_with('t0')
    evrq.realtimeOnly.assert_called_once()
    mock_client.assert_called_once_with(host='ladhost', port=8887, https=False)
    assert result == [{'mocked': 'response'}]


def test_lad_get_eha_builds_query(mocker):
    mock_client, _, mock_eha_query = _patch_lad_query_clients(mocker)
    ehaq = mock_eha_query.return_value

    result = lad_query.lad_get_eha(
        sessionId=7,
        timeout=12,
        channelId='CHAN1',
        timeType=TimeType.ERT,
        startTime='s0',
        endTime='s1',
    )

    ehaq.addChannelId.assert_called_once_with('CHAN1')
    ehaq.useErt.assert_called_once()
    ehaq.before.assert_called_once_with('s1')
    ehaq.after.assert_called_once_with('s0')
    ehaq.addSessionNumber.assert_called_once_with(7)
    ehaq.realtimeOnly.assert_called_once()
    mock_client.assert_called_once_with(host='ladhost', port=8887, https=False)
    assert result == [{'mocked': 'response'}]


def test_lad_get_eha_multi_builds_query(mocker):
    mock_client, _, mock_eha_query = _patch_lad_query_clients(mocker)
    ehaq = mock_eha_query.return_value

    result = lad_query.lad_get_eha_multi(
        sessionId=8,
        timeout=13,
        channelIds=['C1', 'C2', 'C3'],
        timeType=TimeType.SCET,
        startTime='s0',
        endTime='s1',
    )

    ehaq.addChannelId.assert_any_call('C1')
    ehaq.addChannelId.assert_any_call('C2')
    ehaq.addChannelId.assert_any_call('C3')
    ehaq.useScet.assert_called_once()
    ehaq.before.assert_called_once_with('s1')
    ehaq.after.assert_called_once_with('s0')
    ehaq.addSessionNumber.assert_called_once_with(8)
    ehaq.realtimeOnly.assert_called_once()
    mock_client.assert_called_once_with(host='ladhost', port=8887, https=False)
    assert result == [{'mocked': 'response'}]


def test_lad_get_sclkscet(mocker):
    mock_get_times = mocker.patch('core.lad_query.get_sclkscet_times', return_value=('start_sclk', 'end_sclk'))
    mock_get_eha = mocker.patch('core.lad_query.lad_get_eha', return_value=[{'eha': 'data'}])

    result = lad_query.lad_get_sclkscet(99)

    mock_get_times.assert_called_once_with()
    mock_get_eha.assert_called_once_with(99, timeType='ERT', startTime='start_sclk', endTime='end_sclk')
    assert result == [{'eha': 'data'}]
