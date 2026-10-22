import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

import core.decode_1553 as d1553


XML = '''<?xml version="1.0"?>
<root>
  <mil1553_signals>
    <mil1553_signal name="TEST" type="UINT">
      <mil1553_map remote_terminal="9" sub_address="9" transmit_receive="R">
        <data_word_maps>
          <data_word_map word="1" bit_start="0" num_bits="16"/>
        </data_word_maps>
      </mil1553_map>
    </mil1553_signal>
    <mil1553_signal name="INTVAR" type="INT">
      <mil1553_map remote_terminal="9" sub_address="9" transmit_receive="R">
        <data_word_maps>
          <data_word_map word="1" bit_start="0" num_bits="16"/>
        </data_word_maps>
      </mil1553_map>
    </mil1553_signal>
    <mil1553_signal name="POLYVAR" type="UINT">
      <mil1553_map remote_terminal="9" sub_address="9" transmit_receive="R">
        <data_word_maps>
          <data_word_map word="1" bit_start="0" num_bits="16"/>
        </data_word_maps>
      </mil1553_map>
      <polynomial_expansion>
        <factor index="0" coeff="1.0"/>
        <factor index="1" coeff="2.0"/>
      </polynomial_expansion>
    </mil1553_signal>
    <mil1553_signal name="ENUMVAR" type="UINT">
      <mil1553_map remote_terminal="9" sub_address="9" transmit_receive="R">
        <data_word_maps>
          <data_word_map word="1" bit_start="0" num_bits="16"/>
        </data_word_maps>
      </mil1553_map>
      <enums>
        <enum numeric="1" symbol="ONE"/>
      </enums>
    </mil1553_signal>
  </mil1553_signals>
  <extended_signals>
    <extended_signal name="EXT" remote_terminal="9" sub_address="9" transmit_receive="R" word_count="2"/>
  </extended_signals>
</root>
'''

LINE_NORMAL = ('20230328T040949 3 712597947224609 Bus=psyche-A C=0x4925 S=0x4800 '
               'RT=9 SA=9 TR=R WC=01 Err= dt= Data= cc01')
LINE_IRIG = ('001:04:09:49.000000 3 712597947224609 Bus=psyche-A C=0x4925 S=0x4800 '
             'RT=9 SA=9 TR=R WC=01 Err= dt= Data= cc01')
LINE_MULTI_1 = ('20230328T040949 3 712597947224609 Bus=psyche-A C=0x4925 S=0x4800 '
                'RT=9 SA=9 TR=R WC=01 Err= dt= Data= aaaa')
LINE_MULTI_2 = ('20230328T040949 3 712597947224609 Bus=psyche-A C=0x4925 S=0x4800 '
                'RT=9 SA=9 TR=R WC=01 Err= dt= Data= bbbb')


@pytest.fixture
def xml_path(tmp_path):
    p = tmp_path / 'dict.xml'
    p.write_text(XML)
    return str(p)


@pytest.fixture
def log_path(tmp_path):
    p = tmp_path / 'log.txt'
    p.write_text(LINE_NORMAL)
    return str(p)


@pytest.fixture
def multi_log_path(tmp_path):
    p = tmp_path / 'mlog.txt'
    p.write_text(LINE_MULTI_1 + '\n' + LINE_MULTI_2)
    return str(p)


def test_determine_if_word_is_hex():
    assert d1553.determine_if_word_is_hex('cc01') is True
    assert d1553.determine_if_word_is_hex('NORESP') is False
    assert d1553.determine_if_word_is_hex('12345') is True


def test_xml_dictionary_parse(xml_path):
    xd = d1553.XMLdictionary(xml_path)
    var = xd.ParseDictionary('Variable')
    ext = xd.ParseDictionary('Extended_Signal')
    assert 'TEST' in var
    assert 'INTVAR' in var
    assert 'POLYVAR' in var
    assert 'ENUMVAR' in var
    assert 'EXT' in ext
    assert ext['EXT']['word_count'] == '2'


def test_bus_log_msg_non_irig(log_path):
    msg = d1553.BusLogMsg(LINE_NORMAL, 'SCET', None, None, log_path, 'false', None)
    assert msg.time == datetime(2023, 3, 28, 4, 9, 49)
    assert msg.rti == '3'
    assert msg.sclk == 712597947.224609
    assert msg.bus == 'psyche-A'
    assert msg.command == '0x4925'
    assert msg.status_word == '0x4800'
    assert msg.rt == 9
    assert msg.sa == 9
    assert msg.transmit_receive == 'R'
    assert msg.word_count == 1
    assert msg.words == ['cc01']


def test_bus_log_msg_irig(log_path):
    msg = d1553.BusLogMsg(LINE_IRIG, 'SCET', None, None, log_path, 'true', 2023)
    assert msg.time == datetime(2023, 1, 1, 4, 9, 49)
    assert msg.words == ['cc01']


def test_bus_log_msg_filter(log_path):
    msg = d1553.BusLogMsg(LINE_NORMAL, 'SCET', None, None, log_path, 'false', None)
    assert msg.filter(rti=['ALL'], sa=[9], transmit_receive=['R'], rt=[9], bus=['psyche-A']) == (True, True)
    assert msg.filter(rti=['ALL'], sa=[9], transmit_receive=['R'], rt=[9], bus=['other-bus']) == (True, False)
    t0 = datetime(2023, 3, 28, 4, 9, 48)
    t1 = datetime(2023, 3, 28, 4, 9, 50)
    assert msg.filter(start_time=t0, end_time=t1) == (True, True)
    assert msg.filter(start_time=t1) == (False, False)


def test_decode_uint(xml_path, log_path):
    msg = d1553.BusLogMsg(LINE_NORMAL, 'SCET', None, None, log_path, 'false', None)
    var, _ = d1553.read_dict(xml_path)
    value, _ = msg.decode('TEST', var['TEST'])
    assert value == 0xcc01


def test_decode_int(xml_path, log_path):
    msg = d1553.BusLogMsg(LINE_NORMAL, 'SCET', None, None, log_path, 'false', None)
    var, _ = d1553.read_dict(xml_path)
    value, _ = msg.decode('TEST', var['INTVAR'])
    assert value == (0xcc01 - 65536)


def test_get_data_type(xml_path, log_path):
    msg = d1553.BusLogMsg(LINE_NORMAL, 'SCET', None, None, log_path, 'false', None)
    var, _ = d1553.read_dict(xml_path)
    assert msg.get_data_type(var['TEST']) == 'UINT'
    assert msg.get_data_type(var['ENUMVAR']) == 'ENUM'
    assert msg.get_data_type(var['POLYVAR']) == 'polynomial'


def test_get_assumed_year():
    assert d1553.get_assumed_year('/tmp/1553_20230328T040949') == 2023


def test_determine_multi_line():
    multi = {'EXT': {'remote_terminal': '9', 'sub_address': '9', 'transmit_receive': 'R', 'word_count': '2'}}
    is_m, key = d1553.determine_multi_line(False, multi, LINE_MULTI_1)
    assert is_m is True
    assert key == 'EXT'
    is_m, key = d1553.determine_multi_line(True, multi, LINE_MULTI_2, 'EXT')
    assert is_m is True
    assert key == 'EXT'
    # LINE_NORMAL has the same rt/sa/tr as the multi-line definition, so it is also
    # identified as a multi-line entry when scanned from a non-multi-line state.
    is_m, key = d1553.determine_multi_line(False, multi, LINE_NORMAL)
    assert is_m is True
    assert key == 'EXT'


def test_set_word_counter():
    multi = {'EXT': {'word_count': '2'}}
    assert d1553.set_word_counter(None, multi, 'EXT') == 2
    assert d1553.set_word_counter(5, multi, 'EXT') == 5


def test_split_line_data_and_append_to_list():
    data, counter = d1553.split_line_data_and_append_to_list(LINE_NORMAL, [], 2)
    assert data == ['cc01']
    assert counter == 1


def test_decode_by_var(xml_path, log_path):
    msg = d1553.BusLogMsg(LINE_NORMAL, 'SCET', None, None, log_path, 'false', None)
    var, _ = d1553.read_dict(xml_path)
    query = {
        'variables': 'TEST',
        'query_start_time': None,
        'query_end_time': None,
        'sclk_start': None,
        'sclk_end': None,
        'dictionary': xml_path
    }
    result = msg.decode_by_var(var['TEST'], query)
    assert isinstance(result, list)


def test_process_file(xml_path, log_path):
    var, ext = d1553.read_dict(xml_path)
    query = {
        'time_type': 'SCET',
        'irig_status': 'false',
        'assumed_year': None,
        'variables': 'TEST',
        'query_start_time': None,
        'query_end_time': None,
        'sclk_start': None,
        'sclk_end': None,
        'dictionary': xml_path
    }
    result = d1553.process_file(None, None, var['TEST'], ext, [log_path], query)
    assert isinstance(result, list)


def test_read_dict(xml_path):
    var, ext = d1553.read_dict(xml_path)
    assert 'TEST' in var
    assert 'EXT' in ext


def test_decode_1553_log_files(xml_path, log_path):
    info = {
        'assumed_year': None,
        'logfile': [log_path],
        'irig_status': 'false',
        'dictionary': xml_path,
        'time_type': 'SCET',
        'variables': 'TEST',
        'query_start_time': None,
        'query_end_time': None,
        'sclk_start': None,
        'sclk_end': None
    }
    result = d1553.decode_1553_log_files(info, xml_path)
    assert isinstance(result, list)


def test_get_dict_path():
    with patch('core.decode_1553.PathConverter') as MockPC:
        pc = MagicMock()
        MockPC.return_value = pc
        pc.get_matching_paths.return_value = ['/path/dict.xml']
        result = d1553.get_dict_path('/tmpl', '*', '*', 'u')
        assert result == '/path/dict.xml'


def test_get_most_recent_1553_logfiles():
    with patch('core.decode_1553.PathConverter') as MockPC:
        pc = MagicMock()
        MockPC.return_value = pc
        pc.get_1553_bus_logs.return_value = ['/path/log.txt']
        result = d1553.get_most_recent_1553_logfiles('/tmpl', '*', '*', 'u', None, None)
        assert result == ['/path/log.txt']
