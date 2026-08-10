import logging
import sys
from starlette.concurrency import iterate_in_threadpool

def restore_root_logger():
    # restore root logger that was crippled by MTAK
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    for handler in root_logger.handlers:
        handler.setLevel(logging.DEBUG)

def listloggers():
    rootlogger = logging.getLogger()
    print(rootlogger)
    for h in rootlogger.handlers:
        print('     %s' % h)

    for nm, lgr in logging.Logger.manager.loggerDict.items():
        if isinstance(lgr, logging.PlaceHolder):
            print('+ [%-20s] %s' % (nm, lgr))
        else:
            print('+ [%-20s] %s propagate: %s' % (nm, lgr, lgr.propagate))
            for h in lgr.handlers:
                print('     %s' % h)

# import this first since MTAK messes up logging of other modules
from core import venue_core
restore_root_logger()

import os

logger = logging.getLogger(__name__)

def print_env_variables():
    logger.info('ENVIRONMENT VARIABLES:')
    names = [
        'ING_VENUE_DIR',
        'ING_MTAK_DIR',
        'ING_LOG_DIR',
        'CUSTOM_SCRIPT_BASE_DIR',
        'LAD_HOST',
        'LAD_PORT',
        'LAD_HTTPS',
        'BUS_1553_LOGFILE_PATH',
        'LOGFILE_1553_DICTIONARY_FILE_PATH',
        'IRIG_SOURCE',
        'CHILL_GDS',
        'PATH',
        'GDS_JAVA_OPTS'
    ]
    for name in names:
        value = os.environ.get(name)
        logger.info(f'{name}: {value}')

    for index, path in enumerate(sys.path):
        logger.info(f'sys.path {index+1}: {path}')

print_env_variables()

import traceback
import sys
import argparse
import io
import random
import string
import time
import math
import yaml
import json
import pyaml_env
from typing import List
import uvicorn
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.openapi.utils import get_openapi
from fastapi.requests import Request
from fastapi.responses import JSONResponse, FileResponse, Response
# from core import core_util
from core.core_utils import EVRType, ChannelType, AlarmTypeMap, DpStatus
from core.schema import MtakStartBodyModel, FswCmdBodyModel, HwCmdBodyModel, \
    SseCmdBodyModel, BinaryFileBodyModel, ScmfFileBodyModel, \
    EvrRtBodyModel, EvrRtMultiBodyModel, EvrChillBodyModel, EvrChillMultiBodyModel, EVRObjectResp, \
    EhaRtBodyModel, EhaRtMultiBodyModel, EhaChillBodyModel, EhaChillMultiBodyModel, ChannelValueObjectRespModel, \
    DpBodyModel, DataProductObjectRespModel, \
    Parse1553BodyModel, Bus1553LogObject, \
    ScriptStartBodyModel, ScriptStatusBodyModel, ScriptStatusResp, ScriptHaltBodyModel, ScriptRunInfo, \
    HealthStatus, HealthStatusEnum, \
    MtakStartResponse, ErrorResponse, \
    CmdDispatchedResp, TimeType
from fastapi.exceptions import RequestValidationError
import utils

utils.print_key_info()

LOG_CONFIG_YAML = 'log_config.yaml'

prefix_router = APIRouter(prefix='/api/v3')


def check_default_cmd_string(default_cmd_string):
    
  # if string_id is value 'default' set string_id to None. Else, proceed with input string id
  if default_cmd_string in ['A', 'B', 'AB']:
    return default_cmd_string
  else:
    return None


@prefix_router.get('/health', 
                    responses={
                        200: {'model': HealthStatus},
                        400: {'model': ErrorResponse}
                    },
                    summary='Check health status of VenueServer',
                    tags=['HEALTH']
                )
def health() -> HealthStatus:
    # listloggers()
    return HealthStatus(status=HealthStatusEnum.OK.value, message='')


@prefix_router.post('/mtak/start',
                    responses={
                        200: {'model': MtakStartResponse},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Start MTAK on the venue GDS host for the specified AMPCS session ids',
                    tags=['MTAK']
                )
def start_mtak(body: MtakStartBodyModel, response: Response):
    try:
        logger.info('calling core_start_mtak')

        logger.info(f'defaultCmdString: {body.defaultCmdString.value} {type(body.defaultCmdString.value)}')

        sessionIds, startTime = venue_core.core_start_mtak(sessionIds=body.sessionIds,
                                   defaultCmdString=body.defaultCmdString.value,
                                   timeout=body.timeout)

        return MtakStartResponse(sessionIds=sessionIds, startTime=startTime)
    except Exception as ex:
        msg = 'Unexpected error in /mtak/start'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')


@prefix_router.post('/mtak/shutdown', 
                    status_code=204,
                    responses={
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Shutdown MTAK that was started by VenueServer',
                    tags=['MTAK']
                )
def shutdown_mtak(response: Response):
    try:
        venue_core.core_stop_mtak()
        return Response(status_code=204)
    except Exception as ex:
        msg = 'Unexpected error in /mtak/shutdown'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')


@prefix_router.post('/cmd/fsw_cmd',
                    responses={
                        200: {'model': CmdDispatchedResp},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Send a FSW command via MTAK',
                    tags=['COMMAND']
                )
def fsw_cmd(body: FswCmdBodyModel, response: Response):
    try:
        string_selection = check_default_cmd_string(body.stringSelection.value)

        cmdRequested, dispatchTime = venue_core.core_send_fsw_cmd(sessionId=body.sessionId,
                                    validate=body.validate_,
                                    cmdString=body.commandString,
                                    stringSelection=string_selection,
                                    timeout=body.timeout)
        
        return JSONResponse(status_code=200, content={'cmdRequested': cmdRequested, 'dispatchTime': dispatchTime})
    except Exception as ex:
        msg = 'Failed to send FSW command'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')


@prefix_router.post('/cmd/hw_cmd',
                    responses={
                        200: {'model': CmdDispatchedResp},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Send a HW command via MTAK',
                    tags=['COMMAND']
                )
def hw_cmd(body: HwCmdBodyModel, response: Response):
    try:
        string_selection = check_default_cmd_string(body.stringSelection.value)

        cmdRequested, dispatchTime = venue_core.core_send_hw_cmd(sessionId=body.sessionId,
                                    cmdStem=body.commandStem,
                                    stringSelection=string_selection,
                                    timeout=body.timeout)
        return JSONResponse(status_code=200, content={'cmdRequested': cmdRequested, 'dispatchTime': dispatchTime})
    except Exception as ex:
        msg = 'Failed to send HW command'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')

@prefix_router.post('/cmd/sse',
                    responses={
                        200: {'model': CmdDispatchedResp},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Send a SSE command via MTAK',
                    description='Send a SSE (Simulation and Support Equipment) command via MTAK',
                    tags=['COMMAND']
                )
def sse_cmd(body: SseCmdBodyModel, response: Response):
    try:
        cmdRequested, dispatchTime = venue_core.core_send_sse_cmd(sessionId=body.sessionId,
                                    cmdString=body.commandString,
                                    timeout=body.timeout)
        return JSONResponse(status_code=200, content={'cmdRequested': cmdRequested, 'dispatchTime': dispatchTime})
    except Exception as ex:
        msg = 'Failed to send SSE command'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')


@prefix_router.post('/cmd/binary_file',
                    responses={
                        200: {'model': CmdDispatchedResp},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Upload a file to flight computer via MTAK',
                    tags=['COMMAND']
                )
def binary_file(body: BinaryFileBodyModel, response: Response):
    try:
        string_selection = check_default_cmd_string(body.stringSelection.value)
        
        cmdRequested, dispatchTime = venue_core.core_send_fsw_file(
            sessionId=body.sessionId,                                                
            sourcePath=body.sourceFilePath,
            targetLoc=body.targetFilePath,
            fileType=body.fileType,
            overwrite=body.overwrite,
            stringSelection=string_selection,
            timeout=body.timeout)
        return JSONResponse(status_code=200, content={'cmdRequested': cmdRequested, 'dispatchTime': dispatchTime})
    except Exception as ex:
        msg = f'Failed to send a file: {body.sourceFilePath}'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')

    
@prefix_router.post('/cmd/scmf',
                    responses={
                        200: {'model': CmdDispatchedResp},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Upload a SCMF file to flight',
                    tags=['COMMAND']    
                )
def scmf_file(body: ScmfFileBodyModel, response: Response):
    try:        
        cmdRequested, dispatchTime = venue_core.core_send_scmf_file(
            sessionId=body.sessionId,                                                
            filePath=body.filePath,
            disableChecks=body.disableChecks,
            timeout=body.timeout)
        return JSONResponse(status_code=200, content={'cmdRequested': cmdRequested, 'dispatchTime': dispatchTime})
    except Exception as ex:
        msg = f'Failed to send a SCMF file: {body.filePath}'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')


@prefix_router.get('/evr/realtime',
                    responses={
                        200: {'model': List[EVRObjectResp]},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Queries the real time EVR stream for the specified EVRs',
                    description='Queries the AMPCS Global LAD and return an array of EVR objects',
                    tags=['EVR']
                )
def evr_realtime(body: EvrRtBodyModel, response: Response):
    try:
        evr_dicts = venue_core.get_rt_evr(sessionId=body.sessionId,
                                    evrName=body.evrName,
                                    eventId=body.eventId,
                                    evrLevel=body.evrLevel,
                                    timeType=TimeType.ERT, # Use ERT for real time query
                                    startTime=body.startTime,
                                    endTime=body.endTime,
                                    timeout=body.timeout)
        return JSONResponse(status_code=200, content=evr_dicts)

    except Exception as e:
        msg = 'Failed to query realtime EVR'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')

@prefix_router.get('/evr/realtime_multi',
                    responses={
                        200: {'model': List[EVRObjectResp]},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Queries the real time EVR stream for the specified EVRs. This supports querying multiple EVR names, etc.',
                    description='Queries the AMPCS Global LAD and return an array of EVR objects',
                    tags=['EVR']
                )
def evr_realtime_multi(body: EvrRtMultiBodyModel, response: Response):
    try:
        evr_dicts = venue_core.get_rt_evr_multi(sessionId=body.sessionId,
                                    evrNames=body.evrNames,
                                    eventIds=body.eventIds,
                                    evrLevels=body.evrLevels,
                                    timeType=TimeType.ERT, # Use ERT for realtime query
                                    startTime=body.startTime,
                                    endTime=body.endTime,
                                    timeout=body.timeout)
        return JSONResponse(status_code=200, content=evr_dicts)

    except Exception as e:
        msg = 'Failed to query realtime EVR'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')

@prefix_router.get('/evr/chill',
                    responses={
                        200: {'model': List[EVRObjectResp]},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Query EVRs using chill_get_evrs',
                    description='Note that there is no guarantee that EVRs are sorted according to the time.',
                    tags=['EVR']
                )
def evr_chill(body: EvrChillBodyModel, response: Response):
    try:
        evrTypes = []
        for val in body.evrType:
            evrTypes.append(EVRType[val])

        return venue_core.get_chill_evr(sessionId=body.sessionId,
                        evrTypes=evrTypes,
                        evrName=body.evrName,
                        eventId=body.eventId,
                        evrLevel=body.evrLevel,
                        evrModule=body.evrModule,
                        timeType=body.timeType,
                        startTime=body.startTime,
                        endTime=body.endTime,
                        timeout=body.timeout)

    except Exception as e:
        msg = 'Failed to query CHILL EVR'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')
    
@prefix_router.get('/evr/chill_multi',
                    responses={
                        200: {'model': List[EVRObjectResp]},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Query EVRs using chill_get_evrs. This supports querying multiple EVR names, etc.',
                    description='Note that there is no guarantee that EVRs are sorted according to the time.',
                    tags=['EVR']
                )
def evr_chill_multi(body: EvrChillMultiBodyModel, response: Response):
    try:
        evrTypes = []
        for val in body.evrType:
            evrTypes.append(EVRType[val])

        return venue_core.get_chill_evr_multi(sessionId=body.sessionId,
                        evrTypes=evrTypes,
                        evrNames=body.evrNames,
                        eventIds=body.eventIds,
                        evrLevels=body.evrLevels,
                        evrModules=body.evrModules,
                        timeType=body.timeType,
                        startTime=body.startTime,
                        endTime=body.endTime,
                        timeout=body.timeout)

    except Exception as e:
        msg = 'Failed to query CHILL EVR'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')


@prefix_router.get('/eha/realtime',
                    responses={
                        200: {'model': List[ChannelValueObjectRespModel]},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                   summary='Queries the real time telemetry stream for a given channel',
                   description='Queries AMPCS Global LAD and return an array of EHA channel objects',
                   tags=['EHA']
                )
def eha_realtime(body: EhaRtBodyModel, response: Response):
    try:
        eha_dicts = venue_core.get_rt_eha(sessionId=body.sessionId,
                                    channelId=body.channelId,
                                    timeType=TimeType.ERT, # TODO: placeholder for R3
                                    startTime=body.startTime,
                                    endTime=body.endTime,
                                    timeout=body.timeout)
        return JSONResponse(status_code=200, content=eha_dicts)

    except Exception as e:
        msg = 'Failed to query realtime EHA'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')

@prefix_router.get('/eha/realtime_multi',
                    responses={
                        200: {'model': List[ChannelValueObjectRespModel]},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                   summary='Queries the real time telemetry stream for a given channel. This supports querying multiple channel ids, etc.',
                   description='Queries AMPCS Global LAD and return an array of EHA channel objects',
                   tags=['EHA']
                )
def eha_realtime_multi(body: EhaRtMultiBodyModel, response: Response):
    try:
        eha_dicts = venue_core.get_rt_eha_multi(sessionId=body.sessionId,
                                    channelIds=body.channelIds,
                                    timeType=TimeType.ERT, # Use ERT for realtime query
                                    startTime=body.startTime,
                                    endTime=body.endTime,
                                    timeout=body.timeout)
        return JSONResponse(status_code=200, content=eha_dicts)

    except Exception as e:
        msg = 'Failed to query realtime EHA'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')

@prefix_router.get('/eha/chill',
                    responses={
                        200: {'model': List[ChannelValueObjectRespModel]},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },                   
                   summary='Queries channel values from CHILL database',
                   description='Uses chill_get_chanvals and returns an array of EHA channel objects',
                   tags=['EHA']
                )
def eha_chill(body: EhaChillBodyModel, response: Response):
    try:
        chanTypes = []
        for val in body.channelTypes:
            chanTypes.append(ChannelType[val])

        alarmType = None
        if body.inAlarm is not None:
            alarmType = AlarmTypeMap[body.inAlarm.value]

        return venue_core.get_chill_eha(sessionId=body.sessionId,
                                    channelIds=body.channelIds,
                                    channelTypes=chanTypes,
                                    timeType=body.timeType,
                                    startTime=body.startTime,
                                    endTime=body.endTime,
                                    inAlarmFilter=alarmType,
                                    timeout=body.timeout)

    except Exception as e:
        msg = 'Failed to query CHILL EHA'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')

@prefix_router.get('/eha/chill_multi',
                    responses={
                        200: {'model': List[ChannelValueObjectRespModel]},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },                   
                   summary='Queries channel values from CHILL database. This supports querying multiple channel ids, etc.',
                   description='Uses chill_get_chanvals and returns an array of EHA channel objects',
                   tags=['EHA']
                )
def eha_chill_multi(body: EhaChillMultiBodyModel, response: Response):
    try:
        chanTypes = []
        for val in body.channelTypes:
            chanTypes.append(ChannelType[val])

        alarmType = None
        if body.inAlarm is not None:
            alarmType = AlarmTypeMap[body.inAlarm.value]

        return venue_core.get_chill_eha_multi(sessionId=body.sessionId,
                                    channelIds=body.channelIds,
                                    channelTypes=chanTypes,
                                    timeType=body.timeType,
                                    startTime=body.startTime,
                                    endTime=body.endTime,
                                    inAlarmFilter=alarmType,
                                    timeout=body.timeout)

    except Exception as e:
        msg = 'Failed to query CHILL EHA'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')
    
@prefix_router.get('/dp',
                    responses={
                        200: {'model': List[DataProductObjectRespModel]},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Query data products meta data from CHILL database',
                    tags=['DATA_PRODUCT']
                )
def dp_chill(body: DpBodyModel, response: Response):
    try:
        dpStatus = DpStatus.ALL
        if body.dpStatus is not None and body.dpStatus != '':
            dpStatus = DpStatus[body.dpStatus]

        return venue_core.get_dp(sessionId=body.sessionId,
                        dpStatus=dpStatus,
                        apIds=body.apIds,
                        timeType=body.timeType,
                        startTime=body.startTime,
                        endTime=body.endTime,
                        timeout=body.timeout)

    except Exception as e:
        msg = 'Failed to query CHILL Data Products'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')
    

@prefix_router.get('/bus1553',
                    responses={
                        200: {'model': List[Bus1553LogObject]},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Parse Bus 1553 log files to query a variable defined in a Bus 1553 dictionary',
                    description='variables is the name of a single variable, which is defined in a Bus 1553 dictionary.',
                    tags=['BUS_1553']
                )
def decode_1553(body: Parse1553BodyModel, request: Request, response: Response):
    try:
        return venue_core.decode_1553(start_time= body.start_time,
                              end_time=body.end_time,
                              duration=body.duration,
                              time_type=body.time_type,
                              variables=body.variables,
                              username=request.state.username)

    except Exception as e:
        msg = 'Failed to query 1553 Bus log'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')


@prefix_router.post('/custom_script/start', 
                    responses={
                        200: {'model': ScriptRunInfo},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Start execution of a custom script',
                    description='This will start the custom script and return. Use status endpoint to get its status.',
                    tags=['SCRIPT']
                )
def script_start(body: ScriptStartBodyModel, request: Request, response: Response):
    try:
        username = request.state.username
        logger.info(f'username: {username} script_start: {body}')
        body.inputs['username'] = username
        res_dict = venue_core.start_custom_script(script_path=body.scriptPath,
                                      script_hash=body.scriptHash,
                                      inputs=body.inputs,
                                      outputs=body.outputs)
        return JSONResponse(status_code=200, content=res_dict)  
    except Exception as e:
        msg = f'Failed to start a custom script: {body.scriptPath}'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')


@prefix_router.get('/custom_script/{script_run_id}',
                    responses={
                        200: {'model': ScriptStatusResp},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Retrieve status information from currently executing script',
                    tags=['SCRIPT']
                )
def script_status(script_run_id: str, response: Response):
    try:
        res_dict = venue_core.get_custom_script_status(script_run_id=script_run_id)
        return JSONResponse(status_code=200, content=res_dict)

    except Exception as e:
        msg = f'Failed to get the status of custom script: {script_run_id}'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')


@prefix_router.post('/custom_script/{script_run_id}/halt',
                    status_code=204,
                    responses={
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Halt custom script specified',
                    tags=['SCRIPT']
                    )
def script_halt(script_run_id, response: Response):
    try:
        venue_core.halt_custom_script(script_run_id=script_run_id)
        return Response(status_code=204)

    except Exception as e:
        msg = f'Failed to halt custom script: {script_run_id}'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')


@prefix_router.get('/custom_script/{script_run_id}/files',
                    responses={
                        200: {'content': {'application/gzip': {}}},
                        400: {'model': ErrorResponse},
                        401: {'model': ErrorResponse},
                        403: {'model': ErrorResponse}
                    },
                    summary='Download the input, output, and log files of the custom script as tar.gz',
                    tags=['SCRIPT']
                )
def script_file(script_run_id: str, response: Response):
    try:
        tar_gz_path = venue_core.get_custom_script_files(script_run_id=script_run_id)
        filename = os.path.basename(tar_gz_path)
        return FileResponse(tar_gz_path, media_type='application/gzip', filename=filename)

    except Exception as e:
        msg = f'Failed to get custom script files. script_run_id: {script_run_id}'
        logging.exception(msg)
        response.status_code = 400
        return ErrorResponse(message=f'{msg}. {traceback.format_exc()}')


# router needs to be added after end point definitions
app = FastAPI()
app.include_router(prefix_router)


@app.middleware('http')
async def check_jwt(request: Request, call_next):
    request.state.username = ''

    if request.url.path == '/docs':
        # docs end point does not require JWT token
        return await call_next(request)    
    if request.url.path == '/openapi.json':
        # docs end point does not require JWT token
        return await call_next(request)
    if request.url.path == '/openapi.yaml':
        # docs end point does not require JWT token
        return await call_next(request)
    
    if request.url.path.endswith('/health'):
        # health end point does not require JWT token
        return await call_next(request)
    else:
        authorization_header = request.headers.get('Authorization')
        try:
            jwt_decoded = utils.get_decoded_token(authorization_header)
            # cache username info for this request
            # See: https://fastapi.tiangolo.com/tutorial/sql-databases/#about-requeststate
            request.state.username = jwt_decoded.get('username', '')
        except Exception:
            return JSONResponse(status_code=401, 
                content={'message': f'Invalid API token. {traceback.format_exc()}'})

        if utils.has_permission(jwt_decoded):
            return await call_next(request)
        else:
            return JSONResponse(status_code=403, 
                content={
                    'message': f'Does not have the required permission. Need one of {utils.ACCEPTED_SCOPES}'
                })

@app.middleware('http')
async def log_request(request: Request, call_next):
    request_id = ''.join(random.choices(string.ascii_uppercase, k=6))
    logger.info(f'{request_id}: {request.method} {request.url.path}')
    start_time = time.time()
    
    response = await call_next(request)
    
    elapsed_msec = (time.time() - start_time) * 1000
    # username is available after the request has been processed
    username = request.state.username if hasattr(request.state, 'username') else ''

    # response is "StreamingResponse" class. We need to the response content as a string to log.
    # See https://stackoverflow.com/questions/71882419/fastapi-how-to-get-the-response-body-in-middleware
    content_type = response.headers.get('content-type')
    response_content = ''
    if content_type and content_type.lower() == 'application/json':
        response_body = [chunk async for chunk in response.body_iterator]
        response.body_iterator = iterate_in_threadpool(iter(response_body))
        response_content = b''.join(response_body).decode()

    log_max_chars = 1000
    if response.status_code >= 200 and response.status_code < 400:
        if len(response_content) > log_max_chars:
            logger.info(f'{request_id}: completed in {elapsed_msec:.2f} msec.' + 
                        f' status_code: {response.status_code} username: {username} response_content (total_length: {len(response_content)}): {response_content[:log_max_chars]}')
        else:
            logger.info(f'{request_id}: completed in {elapsed_msec:.2f} msec.' + 
                        f' status_code: {response.status_code} username: {username} response_content: {response_content}')
    else:
        logger.warning(f'{request_id}: completed in {elapsed_msec:.2f} msec.' + 
                    f' status_code: {response.status_code} username: {username} response_content: {response_content}')
    
    return response

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc:RequestValidationError):
    error_payload = {"detail": exc.errors()}
    return JSONResponse(status_code=400,
        content=error_payload)


### OPENAPI ###

tags_metadata = [
    {
        'name': 'MTAK',
        'description': 'Start or stop MTAK sessions'
    },
    {
        'name': 'COMMAND',
        'description': 'Send commands'
    },
    {
        'name': 'EVR',
        'description': 'Query EVR telemetry'
    },
    {
        'name': 'EHA',
        'description': 'Query EHA telemetry'
    },
    {
        'name': 'DATA_PRODUCT',
        'description': 'Query data products'
    },
    {
        'name': 'BUS_1553',
        'description': 'Query 1553 bus logs'
    },
    {
        'name': 'SCRIPT',
        'description': 'Run custom scripts'
    },
    {
        'name': 'HEALTH',
        'description': 'Check service health'
    }
]

@app.get('/openapi.yaml', include_in_schema=False)
def openapi_yaml() -> Response:
    # Convert API specs in JSON to YAML.
    # See https://github.com/tiangolo/fastapi/issues/1140
    specs_json= app.openapi()
    yaml_str_io = io.StringIO()
    yaml.dump(specs_json, yaml_str_io)
    return Response(yaml_str_io.getvalue(), media_type='text/yaml')

def custom_openapi():
    try:
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title='Ingenium Venue Agent AMPCS',
            version='15.0',
            description='RESTful API of Ingenium Venue Agent (AMPCS) that interfaces with test venues',
            routes=app.routes,
            tags=tags_metadata
        )

        for _, method_item in openapi_schema.get('paths').items():
            for _, param in method_item.items():
                responses = param.get('responses')
                # remove the default 422 response fro OpenAPI, which was overriden as 400 response
                if '422' in responses:
                    del responses['422']
        # cache the schema
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    except:
        logger.error(traceback.format_exc())

# override openapi method
app.openapi = custom_openapi

def parse_args():
    parser = argparse.ArgumentParser(description='Ingenium Venue Agent AMPCS',
        prog='main.py',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--port', '-p', type=int, default=19443,
                        help='port number of the service')
    return parser.parse_args()

if __name__ == '__main__':
    log_config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), LOG_CONFIG_YAML))
    if os.path.isfile(log_config_path):
        logger.info(f'Load log configuration from: {log_config_path}')
    else:
        logger.error(f'Log configuration file does not exist. Exit. {log_config_path}')
        sys.exit(1)
    try:
        log_config = pyaml_env.parse_config(log_config_path)
    except Exception as ex:
        logger.exception(f'Failed to load log configuration file: {log_config_path}')
        sys.exit(1)

    args = parse_args()
    
    uvicorn.run('main:app', host='127.0.0.1', port=args.port, reload=False, log_config=log_config, workers=1)
