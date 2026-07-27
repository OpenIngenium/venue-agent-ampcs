from pydantic import BaseModel, Field, Extra, validator
from typing import List, Union
from enum import Enum
from pathlib import Path

class DefaultCmdString(str, Enum):
    A = 'A'
    B = 'B'
    AB = 'AB'

class HealthStatusEnum(str, Enum):
    OK = 'OK'
    ERROR = 'ERROR'
    UNKNOWN = 'UNKNOWN'

class HealthStatus(BaseModel):
    status: HealthStatusEnum = Field(description='health status')
    message: str = Field(description='status message')

class ErrorResponse(BaseModel):
    message: str = Field('', description='Error message')

class MtakStartBodyModel(BaseModel):
    sessionIds: List[int] = Field(description='AMPCS session ids to start MTAK on')
    timeout: int = Field(30, ge=25,
        description='How long to wait until timeout in seconds. The minimum is 25 seconds since MTAK takes some time to start')
    defaultCmdString: DefaultCmdString = Field(DefaultCmdString.AB, 
        description='Which sides of flight computer the command is for. This will be used if default is used for stringSelection.')

class MtakStartResponse(BaseModel):
    sessionIds: List[int] = Field(description='AMPCS session ids')
    startTime: str = Field(description='Time that MTAK started')

class StringSelection(str, Enum):
    DEFAULT = 'DEFAULT'
    A = 'A'
    B = 'B'
    AB = 'AB'

class FswCmdBodyModel(BaseModel):
    sessionId: int = Field(description='The AMPCS session to send the command through')
    commandString: str = Field(description='The command string including the command stem and any arguments')
    # need to prepend underscore to avoid name conflict with built-in property of Pydantic
    validate_: bool = Field(True, alias='validate', 
        description='Flag for AMPCS to validate the command against the FSW dict before radiating')
    stringSelection: StringSelection = Field(StringSelection.DEFAULT,
        description='Which sides of flight computer the command is for')
    timeout: int = Field(10, ge=0, description='The timeout on the dispatch process in seconds')

class CmdDispatchedResp(BaseModel):
    cmdRequested: str = Field('', 
        description='This mirrors what was received as the requested command string')
    # time format was checked
    dispatchTime: str = Field('', 
        description='Time that the dispatch occurred. Example: 2017-09-25T03:57:42.676Z') 

class HwCmdBodyModel(BaseModel):
    sessionId: int = Field(description='The AMPCS session to send this file through')
    commandStem: str = Field(description='The command stem of the HW Command')
    stringSelection: StringSelection = Field(StringSelection.DEFAULT, 
        description='Specifies the MTAK string to send the command')
    timeout: int = Field(10, ge=0, 
        description='The timeout on the dispatch process in seconds')

class SseCmdBodyModel(BaseModel):
    sessionId: int = Field(description='The AMPCS session to send the command through')
    commandString: str = Field(description='The command string including the command stem and any arguments')
    timeout: int = Field(10, ge=0, description='The timeout on the dispatch process in seconds')

class BinaryFileBodyModel(BaseModel):
    sessionId: int = Field(description='The AMPCS session to send the command through')
    sourceFilePath: str = Field(description='The full path on GDS host (ex: /proj/europa/sit/current/files/myfile.data)')
    targetFilePath: str = Field(description='The full onboard path (i.e. /eng1/myfile.data')
    overwrite: bool = Field(True, description='if True will overwrite any existing onboard file')
    fileType: int = Field(description='The file type that should be used to build the binary file into a SCMF')
    stringSelection: StringSelection = Field(StringSelection.DEFAULT, 
        description='Specifies the MTAK string to send the command')
    timeout: int = Field(10, ge=0, 
        description='The timeout on the dispatch process in seconds')

class ScmfFileBodyModel(BaseModel):
    sessionId: int = Field(description='The AMPCS session to send the command through')
    filePath: str = Field(description='The full path on GDS host (ex: /proj/europa/sit/current/files/myfile.scmf)')
    disableChecks: bool = Field(False, description='Disables the check done by AMPCS for invalid scmf file')
    timeout: int = Field(10, ge=0, description='The timeout on the dispatch process in seconds')

class EvrRtBodyModel(BaseModel):
    sessionId: int = Field(description='The AMPCS session to qury against')
    # wild card works
    evrName: Union[str, None] = Field(None, description='Name of EVRs to query. Wildcard * can be used.')
    eventId: Union[int, None] = Field(None, description='EVR event ID')
    evrLevel: Union[str, None] = Field(None, 
        description='Filter by EVR level. Wildcard * can be used. Note that EVR levels are project specific.')
    startTime: str = Field(description='Query start time in ERT DOY UTC (2009-202T12:35:00)')
    endTime: str = Field(description='Query end time in ERT DOY UTC (2009-202T12:35:00)')
    timeout: int = Field(240, ge=0, description='How long to wait in seconds for results to return')

class EvrRtMultiBodyModel(BaseModel):
    sessionId: int = Field(description='The AMPCS session to qury against')
    # wild card works
    evrNames: List[str] = Field([], 
        description='Name of EVRs to retrieve. No wildcard is supported')
    eventIds: List[int] = Field([], 
        description='Event IDs of EVRs to retreive')
    evrLevels: List[str] = Field([], 
        description='Levels of EVRs to return. Note that levels are project specific.')
    startTime: str = Field(description='Query start time in ERT DOY UTC (2009-202T12:35:00)')
    endTime: str = Field(description='Query end time in ERT DOY UTC (2009-202T12:35:00)')
    timeout: int = Field(240, ge=0, description='How long to wait in seconds for results to return')

class EvrType(str, Enum):
    FSW_REALTIME = 'FSW_REALTIME'
    FSW_RECORDED = 'FSW_RECORDED'
    SSE = 'SSE'

class EhaType(str, Enum):
    FSW_REALTIME = 'FSW_REALTIME'
    FSW_RECORDED = 'FSW_RECORDED'
    SSE = 'SSE'

class AlarmType(str, Enum):
    RED_ALARM = 'RED_ALARM'
    YELLOW_ALARM = 'YELLOW_ALARM'
    ANY_ALARM = 'ANY_ALARM'

class TimeType(str, Enum):
    ERT = 'ERT'
    SCET = 'SCET'
    SCLK = 'SCLK'


class TimeType1553(str, Enum):
    SCET = 'SCET'
    SCLK = 'SCLK'

class EvrChillBodyModel(BaseModel):
    sessionId: int = Field(description='The AMPCS session to query against')
    evrType: List[EvrType] = Field([], 
        description='The type of EVRs to query. If not specified, will query FSW realtime and recorded EVRs')
    evrName: str = Field(None, 
        description='Name of EVRs to retrieve. SQL style pattern can be used such as % as a wildcard')
    eventId: int = Field(None, 
        description='Event IDs of EVRs to retreive')
    evrLevel: str = Field(None, 
        description='Level of EVRs to return. Note that levels are project specific and requesting a level that does not exist will return nothing')
    evrModule: str = Field(None, description='Module of EVRs to retreive')
    # Note: no guarantee that EVRs are sorted by time
    timeType: TimeType = Field(TimeType.ERT, description='The time type to use to query')
    startTime: str = Field(None, description='Query start time. For SCET/ERT: 2009-202T12:35:00 (UTC). For SCLK: 0410313966 (second resolution only)')
    endTime: str = Field(None, description='Query end time. For SCET/ERT: 2009-202T12:35:00 (UTC). For SCLK: 0410313966 (second resolution only)')
    timeout: int = Field(240, ge=0, description='How long to wait in seconds for results to return')

class EvrChillMultiBodyModel(BaseModel):
    sessionId: int = Field(description='The AMPCS session to query against')
    evrType: List[EvrType] = Field([], 
        description='The type of EVRs to query. If not specified, will query FSW realtime and recorded EVRs')
    evrNames: List[str] = Field([], 
        description='Name of EVRs to retrieve. No wildcard is supported')
    eventIds: List[int] = Field([], 
        description='Event IDs of EVRs to retreive')
    evrLevels: List[str] = Field([], 
        description='Levels of EVRs to return. Note that levels are project specific.')
    evrModules: List[str] = Field([], description='Modules of EVRs to retreive')
    # Note: no guarantee that EVRs are sorted by time
    timeType: TimeType = Field(TimeType.ERT, description='The time type to use to query')
    startTime: str = Field(None, description='Query start time. For SCET/ERT: 2009-202T12:35:00 (UTC). For SCLK: 0410313966 (second resolution only)')
    endTime: str = Field(None, description='Query end time. For SCET/ERT: 2009-202T12:35:00 (UTC). For SCLK: 0410313966 (second resolution only)')
    timeout: int = Field(240, ge=0, description='How long to wait in seconds for results to return')

class EVRObjectResp(BaseModel):
    evrName: str = Field('', description='Name of the EVR')
    sessionId: int = Field(0, description='The AMPCS session ID')
    vcId: int = Field(0, description='The virtual channel ID')
    eventId: int = Field(0, description='EVR event ID')
    evrLevel: str = Field('', description='Level of EVR')
    fromSSE: bool = Field(False, description='True if EVR is frome SSE, false otherwise')
    evrMessage: str = Field('', description='Message that this EVR contains')
    evrModule: str = Field('', description='FSW module that generated this EVR')
    sclk: str = Field('', description='SCLK for this EVR')  # sclk is a string in response
    ert: str = Field('', description='Earth received (ISO-formatted) time')
    scet: str = Field('', description='ISO-formatted spacecraft event time')
    isRecorded: bool = Field(False, description='True if this is a recorded EVR (from data products)')

class ChannelValueObjectRespModel(BaseModel):
    dn: str = Field('', description='Data number value. Only returns string for now')
    eu: float = Field(0.0, description='Engineering unit value')
    channelId: str = Field('', description='The Id of the EHA channel')
    sessionId: int = Field(0, description='The AMPCS session ID that the result came from')
    vcId: int = Field(0, description='The virtual channel ID that the result came from')
    channelName: str = Field('', description='The name of the EHA channel')
    channelType: str = Field('', description='The type of the EHA channel')
    channelStatus: str = Field('', description='The string status of the channel if it is a table-driven channel (only for boolean and status type channels)')
    sclk: str = Field('', description='SCLK when this value was read')   # sclk is a string in response
    ert: str = Field('', description='Earth received (ISO-formatted) time when this value was received')
    scet: str = Field('', description='Correlated SCLK time in ISO format')
    isRecorded: bool = Field(False, description='True if this is a recorded EHA, false otherwise')
    dnAlarmState: str = Field('', description='Indicates if the channel measurement is in alarm (on DN values)')
    euAlarmState: str = Field('', description='Indicates if the channel measurement is in alarm (on EU values)')

class EhaRtBodyModel(BaseModel):
    sessionId: Union[int, None] = Field(None, description='The AMPCS session to query against')
    channelId: Union[str, None] = Field(None, description='The channel ID to search for')
    # startTime is required
    startTime: str = Field(description='Query start time in ERT DOY UTC (2009-202T12:35:00)')
    # endTime is required
    endTime: str = Field(description='Query end time in ERT DOY UTC (2009-202T12:35:00)')
    timeout: int = Field(240, ge=0, description='How long to wait in seconds for results to return')

class EhaRtMultiBodyModel(BaseModel):
    sessionId: Union[int, None] = Field(None, description='The AMPCS session to query against')
    channelIds: List[str] = Field(description='The channel IDs to search for')
    # startTime is required
    startTime: str = Field(description='Query start time in ERT DOY UTC (2009-202T12:35:00)')
    # endTime is required
    endTime: str = Field(description='Query end time in ERT DOY UTC (2009-202T12:35:00)')
    timeout: int = Field(240, ge=0, description='How long to wait in seconds for results to return')

class EhaChillBodyModel(BaseModel):
    # chill_get_chanvals does not require sessionId. But such query would result in a very long query time. So, require it.
    sessionId: int = Field(description='The AMPCS session to query against')
    channelIds: List[str] = Field([], description='The channel IDs to search for')
    channelTypes: List[EhaType] = Field([], 
        description='The channel types to query. If not provided, will query FSW realtime and recorded.')
    timeType: TimeType = Field(TimeType.ERT, 
        description='The time format to use to query and to sort the resulting values')
    startTime: Union[str, None] = Field(None, 
        description='Query start time. For SCET/ERT: 2009-202T12:35:00 (UTC). For SCLK: 0410313966 (second resolution only)')
    endTime: Union[str, None] = Field(None, 
        description='Query end time. For SCET/ERT: 2009-202T12:35:00 (UTC). For SCLK: 0410313966 (second resolution only)')
    timeout: int = Field(240, ge=0, description='How long to wait in seconds for results to return')
    inAlarm: AlarmType = Field(None, description='Filter resulting channels based on alarm status')

class EhaChillMultiBodyModel(BaseModel):
    # chill_get_chanvals does not require sessionId. But such query would result in a very long query time. So, require it.
    sessionId: int = Field(description='The AMPCS session to query against')
    channelIds: List[str] = Field([], description='The channel IDs to search for')
    channelTypes: List[EhaType] = Field([], 
        description='The channel types to query. If not provided, will query FSW realtime and recorded.')
    timeType: TimeType = Field(TimeType.ERT, 
        description='The time format to use to query and to sort the resulting values')
    startTime: Union[str, None] = Field(None, 
        description='Query start time. For SCET/ERT: 2009-202T12:35:00 (UTC). For SCLK: 0410313966 (second resolution only)')
    endTime: Union[str, None] = Field(None, 
        description='Query end time. For SCET/ERT: 2009-202T12:35:00 (UTC). For SCLK: 0410313966 (second resolution only)')
    timeout: int = Field(240, ge=0, description='How long to wait in seconds for results to return')
    inAlarm: AlarmType = Field(None, description='Filter resulting channels based on alarm status')

class Dpstatus(str, Enum):
    ALL = 'ALL'
    COMPLETE = 'COMPLETE'
    PARTIAL = 'PARTIAL'
class DpBodyModel(BaseModel):
    # sessionId is required
    sessionId: int = Field(description='The AMPCS session to query against')
    dpStatus: Dpstatus = Field(Dpstatus.ALL, description='Data product status')
    apIds: List[int] = Field([], description='APID of data product to be retrieved')
    timeType: TimeType = Field(TimeType.ERT, description='The time type to use to query')
    # startTime is optional
    startTime: Union[str, None] = Field(None, 
        description='Query start time. For SCET/ERT: 2009-202T12:35:00 (UTC). For SCLK: 0410313966 (second resolution only)')
    # endTime is optional
    endTime: Union[str, None] = Field(None,
        description='Query end time. For SCET/ERT: 2009-202T12:35:00 (UTC). For SCLK: 0410313966 (second resolution only)')
    timeout: int = Field(240, ge=0, description='How long to wait in seconds for results to return')

class DataProductObjectRespModel(BaseModel):
    sessionId: int = Field(0, description='The AMPCS session ID')
    vcId: int = Field(0, description='The virtual channel ID')
    dpStatus: str = Field('', description='Data product status')
    apId: int = Field(0, description='APID of data product to be retrieved')
    apIdProductType: str = Field('', description='Name of the data product type per apid.xml')
    filePath: str = Field('', description='Data product file path')
    fileSize: int = Field(0, description='Data product file size')
    creationTime: str = Field('', description='The time the product was created on the ground, which is slightly different from the time the packets are received (ERT)')
    sclk: str = Field('', description='SCLK for this product')
    ert: str = Field('', description='Earth received (ISO-formatted) time when this product was received')
    scet: str = Field('', description='ISO-formatted spacecraft event time when this product was created')

class Parse1553BodyModel(BaseModel):
    start_time: str = Field(None, description='The start time indicates the earliest record that will be parsed.'
          ' SCET: "2009-202T12:35:00" DOY or "2009-01-20T12:00:00" ISO formats are accepted.'
          ' SCLK: "0410313966.123"')
    end_time: str = Field(None, description='The end time indicates the earliest record that will be parsed.'
          ' SCET: "2009-202T12:35:00" DOY or "2009-01-20T12:00:00" ISO formats are accepted.'
          ' SCLK: "0410313966.123"')
    duration: int = Field(None, description='Number of seconds elapsed from start time, used to establish an end time')
    time_type: TimeType1553 = Field(TimeType1553.SCET, description='Time type for the query start and end time')
    # variables is required
    variables: str = Field(description='Variable name used to parse 1553 log file')

class Bus1553LogObject(BaseModel):
    variables: str = Field('', description='1553 dictionary variable name')
    rti: int = Field(0, description='Return time interval')
    time_scet: str = Field('', description='SCET time record for log file entry')
    # This is a str (the old swagger spec is not correct)
    time_sclk: str = Field('', description='SCLK time record for log file entry')
    bus_name: str = Field('', description='Serial bus name')
    status_word: str = Field('', description='Status word field for the log file entry')
    error_status: str = Field('', description='Error status for the log file entry')
    data_type: str = Field('', description='The response type for the parsed log entry. UINT, HEX, BIN, etc.')
    data_value: str = Field('', description='Parsed log files are evaluated based on their data type.' 
        ' For enums, the data value correlates to a converted value.')
    converted_value: str = Field('', description='Readable representation of the data value')
    dictionary: str = Field('', description='Path to Bus 1553 xml dictionary used to decode the log file')
    log_file: str = Field('', description='1553 log file located in GDS')

class ScriptStartBodyModel(BaseModel):
    scriptName: str = Field(description='Name of custom script')
    scriptPath: str = Field(description='Relative path of custom script from custom script root directory')
    scriptHash: str = Field(description='SHA256 hash of custom script file')
    # service accepts empty inputs
    inputs: dict = Field({}, description='Dictionary of custom script inputs and corresponding values')
    # service accepts empty outputs
    outputs: dict = Field({}, description='Dictionary of custom script outputs')

    # This checks to ensure that the custom script location doesn't include an absolute path, or path short cuts
    @validator('scriptPath')
    def script_path_must_be_relative(cls, v:str)->str:
        if Path(v).is_absolute():
            raise ValueError('scriptPath must be relative path, not an absolute path')
        if ".." in Path(v).parts:
            raise ValueError('scriptPath must not include ..')
        if "~" in Path(v).parts:
            raise ValueError('scriptPath must not include ~')
        return v

class ScriptRunInfo(BaseModel):
    scriptRunId: str = Field(description='id of the running script')
    
class ScriptStatusBodyModel(BaseModel):
    scriptRunId: str = Field(description='custom script ID for the running custom script')

class CustomScriptStatus(str, Enum):
    PENDING = 'PENDING'
    ERROR = 'ERROR'
    PASS = 'PASS'
    FAIL = 'FAIL'

class VerificationStatus(str, Enum):
    PENDING = 'PENDING'
    ERROR = 'ERROR'
    PASS = 'PASS'
    FAIL = 'FAIL'

class ScriptEntriesModel(BaseModel):
    verification_status: VerificationStatus = Field(VerificationStatus.PENDING, 
        description='Verification status for the specified entry')
    entry_outputs: dict = Field({}, description='Custom script entry outputs')
    entry_output_array: List[dict] = Field([], description='Custom script entry output array')

class CustomScriptOutputs(BaseModel):
    outputs: dict = Field({}, description='Custom script outputs fields')
    output_array: List[dict] = Field([], description='Custom script output array')
    entries: ScriptEntriesModel = Field({}, description='Custom script entries')

class ScriptStatusResp(BaseModel):
    logfile_url: str = Field('', description='Relative URL of download end point of logs. "custom_script/{script_run_id}/files"')
    logfile_path: str = Field('', description='The absolute path (on GDS host) to the custom script log file')
    custom_script_status: CustomScriptStatus = Field(CustomScriptStatus.PENDING, 
        description='The current status of the executed custom script')
    custom_script_outputs: CustomScriptOutputs = Field({}, 
        description='Object that contains all current output values from the executed custom script')
    logfile_lines: List[str] = Field([], description='last 25 lines of the custom script log file')

class ScriptHaltBodyModel(BaseModel):
    scriptRunId: str = Field(description='custom script ID for the running custom script')
