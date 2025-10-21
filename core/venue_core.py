# import mtak first since this messes up logging
from .mtak_cmd import mtak_startup_timeout, mtak_shutdown, \
  mtak_send_fsw_cmd, mtak_send_hw_cmd, mtak_send_sse_cmd, \
  mtak_send_fsw_file, mtak_send_scmf_file

from typing import List, Dict

import logging
logger = logging.getLogger(__name__)

import os
import sys
import stat
import re
import redis
import tailer
import json
import hashlib
import psutil
import signal
import uuid
import tarfile
import bitstring
import glob
from datetime import datetime
import subprocess

import traceback
import time
from .core_utils import str2bool, EVRType, ChannelType, AlarmTypeMap, DpStatus, get_env, \
  get_now_isoZ, doyToIsoZ, normalize_with_microsecs, get_csv_row_reader, \
  return_validated_start_end_times, doys_for_lookback, TimeParsingError, \
  most_recent_datetime, utc_now_doy, validate_time, command_type_mapping
from .schema import TimeType
from . import chill_query
from . import lad_query
from .decode_1553 import get_dict_path, get_most_recent_1553_logfiles, \
  get_assumed_year, decode_1553_log_files
CUSTOM_SCRIPT_LOG_PATH_BASE='/tmp/cs'

_custom_script_base_dir = get_env('CUSTOM_SCRIPT_BASE_DIR')
_bus_1553_logfile_path= get_env("BUS_1553_LOGFILE_PATH")
_logfile_1553_dictionary_file_path = get_env("LOGFILE_1553_DICTIONARY_FILE_PATH")
_irig_source= get_env("IRIG_SOURCE")


def _load_json_with_retry(path: str, max_attempts: int = 5, delay: float = 0.1):
    """
    This function will retry the loading of a json file (specifically output.json) in case it is being actively written
    to when the load attempt starts.

    """

    attempt = 0
    while attempt < max_attempts:
        try:
            with open(path, 'r') as file:
                data = json.load(file)
                return data
        except json.JSONDecodeError as er:
            msg = f"JSON decode failed on attempt {attempt + 1}/{max_attempts} for {path}: {er} - retrying"
            logger.debug(msg)
        attempt += 1
        time.sleep(delay * (2 * attempt))
    raise RuntimeError(f"unable to read a consistent JSON file from {path}")


def core_start_mtak (sessionIds, defaultCmdString, timeout):
  '''

  Launches uplink and downlink proxies

  :param sessionIds: session key/Id (int)
  :param timeout: how long to wait for mtak before exiting (int). Minimum 25 seconds
  :return: MTAK response per spec
  '''
  startTimeStr = get_now_isoZ()
  logger.info(f"SessionIds: {sessionIds}")
  mtak_startup_timeout(sessionIds=sessionIds,
                                defaultCmdString=defaultCmdString,
                                timeout_sec=timeout)
  
  return (sessionIds, startTimeStr)



def core_stop_mtak ():
  ''' Stops the uplink and downlink proxies '''

  logger.info(f"calling mtak_shutdown")
  mtak_shutdown()

  return ''

def core_send_fsw_cmd (sessionId, cmdString, validate, stringSelection, timeout=None):
  '''

  Sends flight software command using MTAK

  :param sessionId: session key for mpcs session to send fsw cmd to (int)
  :param cmdString: actual fsw cmd (string)
  :param timeout: amount of time (int)

  :return: (cmdString, dispatchTimeStr)

  '''
  dispatchTimeStr = get_now_isoZ()

  mtak_send_fsw_cmd(sessionId=sessionId,
                    cmdString=cmdString,
                    validate=validate,
                    stringSelection=stringSelection,
                    timeout_sec=timeout)
  return (cmdString, dispatchTimeStr)

def core_send_hw_cmd (sessionId, cmdStem, stringSelection, timeout=None):
  '''
  Sends hardware command using MTAK

  :param sessionId: session key for mpcs session to send fsw cmd to (int)
  :param cmdStem: actual hw cmd (string)
  :param timeout: amount of time (int)

  :return: (cmdStem, dispatchTimeStr)

  '''
  dispatchTimeStr = get_now_isoZ()

  mtak_send_hw_cmd(sessionId=sessionId,
                  cmdStem=cmdStem,
                  stringSelection=stringSelection,
                  timeout_sec=timeout)
  return (cmdStem, dispatchTimeStr)

def core_send_sse_cmd (sessionId, cmdString, timeout=None):
  '''
  Sends SSE command using MTAK

  :param sessionId: session key for mpcs to send sse cmd to (int)
  :param cmdString: actual sse cmd (string)
  :param socketPort: the socket to send data to (int)
  :param timeout: amount of time (int)

  :return: (cmdString, dispatchTimeStr)

  '''
  dispatchTimeStr = get_now_isoZ()

  mtak_send_sse_cmd(sessionId=sessionId,
                  cmdString=cmdString,
                  timeout_sec=timeout)
  return (cmdString, dispatchTimeStr)

def core_send_fsw_file (sessionId, sourcePath, targetLoc, fileType, overwrite, stringSelection, timeout=None):
  '''
  Sends FSW file using MTAK

  :param sessionId: AMPCS session to send this file through (int)
  :param sourcePath: full path on venue's file system to locate the file (string)
  :param targetLoc: full path on the vehicle's file system to send the file (string)
  :param fileType: file type to build binary file into SCMF (int)
  :param overwrite: True if this file should overwrite existing file in targetLoc (boolean)
  :param timeout: timeout on the dispatch process (int)

  :return: (cmdInfo, dispatchTimeStr)

  '''
  dispatchTimeStr = get_now_isoZ()

  mtak_send_fsw_file(sessionId=sessionId,
                          sourcePath=sourcePath,
                          targetLoc=targetLoc,
                          fileType=fileType,
                          overwrite=overwrite,
                          stringSelection=stringSelection,
                          timeout_sec=timeout)
  
  return (
    f'sourcePath: {sourcePath} targetLoc: {targetLoc} fileType: {fileType} overwrite: {overwrite}', 
    dispatchTimeStr
  )

def core_send_scmf_file(sessionId, filePath, disableChecks, timeout=None):
  '''

  Sends flight software SCMF file using MTAK

  :param sessionId: session key for mpcs session to send scmf file (integer)
  :param filePath: full path on venue's file system to file (string)
  :param disableChecks: disables AMPCS check of the scmf (boolean)
  :param timeout: timeout on the dispatch process (int)

  :return: (cmdInfo, dispatchTimeStr)

  '''
  dispatchTimeStr = get_now_isoZ()

  mtak_send_scmf_file(sessionId=sessionId,
                      filePath=filePath,
                      disableChecks=disableChecks,
                      timeout_sec=timeout)
  return (f'SCMF: {filePath} disableChecks: {disableChecks}', dispatchTimeStr)

def checkSessionId(sessionId):
  if (not isinstance(sessionId, int)):
    raise ValueError("Invalid sessionId. Should be an integer.")


def get_evr_dict(sessionId, eventId, vcId, evrName, evrLevel, fromSSE,
              evrMessage, evrModule, sclk, ert, scet, isRecorded):
  checkSessionId(sessionId)
  return {
    'sessionId': sessionId,
    'evrName': evrName,
    'vcId': vcId,
    'eventId': eventId,
    'evrLevel': evrLevel,
    'fromSSE': fromSSE,
    'evrMessage': evrMessage,
    'evrModule': evrModule,
    'sclk': sclk,
    'ert': ert,
    'scet': scet,
    'isRecorded': isRecorded
  }

def get_rt_evr(sessionId, timeout, evrName=None, eventId=None,
              evrLevel=None, timeType:TimeType=None, startTime=None,
              endTime=None):
  '''
  Dispatches realtime evr query to globallad, validates output, and generates response
  based on spec for evr response

  Keyword arguments:
  sessionId -- single testKey or session Id (int)
  evrName  -- name or name pattern of evrs to match (string)
  eventId  -- EVR event ID (int)
  evrLevel -- EVR level (string)
  timeType -- Should be one of TimeType enum
  startTime -- Begin time of range (string)
  endTime  -- End time of range (string)

  Time format for all time types except SCLK (in GMT) is YYYY-DOYThh:mm:ss.ttt

  Returns:
  Python dictionary of EvrResponse

  '''

  try:
    start_dt = datetime.strptime(startTime, '%Y-%jT%H:%M:%S')
    end_dt = datetime.strptime(endTime, '%Y-%jT%H:%M:%S')
  except ValueError as ex:
    msg = "Expected DOY format with integer seconds - ex:2017-310T19:27:13"
    logger.exception(msg)
    raise Exception(msg) from ex

  if (start_dt > end_dt):
    msg = "startTime is after endTime"
    raise Exception(msg)

  try:
    evrs = lad_query.lad_get_evr(sessionId=sessionId, evrName=evrName,
                        eventId=eventId, evrLevel=evrLevel,
                        timeType=timeType, startTime=startTime,
                        endTime=endTime, timeout=timeout)

  except Exception as ex:
    msg = 'Error when querying evrs from GlobalLad'
    logger.error(traceback.format_exc())
    raise Exception(msg) from ex




  logger.info("Found %d EVR results from GlobalLad." %(len(evrs)))

  # convert data to format required by server spec
  evr_dicts = []

  for evr in evrs:
    evr_dict = get_evr_dict(sessionId=int(evr['sessionNumber']),
                  eventId=int(evr['evrId']),
                  vcId=(int(evr['vcid']) if (evr['vcid'] != "") else None),
                  evrName=str(evr['evrName']),
                  evrLevel=str(evr['evrLevel']),
                  fromSSE=(not str2bool(evr['isFsw'])),
                  evrMessage=str(evr['message']),
                  evrModule=None,
                  sclk=str(evr['sclk']),
                  ert=doyToIsoZ(normalize_with_microsecs(evr['ert'])),
                  scet=doyToIsoZ(normalize_with_microsecs(evr['scet'])),
                  isRecorded=(not str2bool(evr['isRealTime'])))
    evr_dicts.append(evr_dict)
  return evr_dicts


def get_rt_evr_multi(sessionId: int, timeout: int, evrNames: List[str]=[], eventIds: List[int]=[],
              evrLevels: List[str]=[], timeType:TimeType=None, startTime=None,
              endTime=None) -> List[Dict]:
  '''
  Queries for EVR using GLAD client. More than one EVR name can be queried.
  Time format for all time types except SCLK (in GMT) is YYYY-DOYThh:mm:ss.ttt

  Parameters
  ------------------
  sessionId:
    AMPCS session id
  timeout:
    Time to wait in seconds before returning timeout
  evrNames:
    names of evrs to match. No wildcard is supported.
  eventIds:
    EVR event ids
  evrLevels:
    EVR levels
  timeType:
    Should be one of TimeType
  startTime:
    Begin time of query range
  endTime:
    End time of query range

  Returns:
  List[Dict]
    list of evrs in dict
  '''

  try:
    start_dt = datetime.strptime(startTime, '%Y-%jT%H:%M:%S')
    end_dt = datetime.strptime(endTime, '%Y-%jT%H:%M:%S')
  except ValueError as ex:
    msg = "Expected DOY format with integer seconds - ex:2017-310T19:27:13"
    logger.exception(msg)
    raise Exception(msg) from ex

  if (start_dt > end_dt):
    msg = "startTime is after endTime"
    raise Exception(msg)

  try:
    evrs = lad_query.lad_get_evr_multi(sessionId=sessionId, evrNames=evrNames,
                        eventIds=eventIds, evrLevels=evrLevels,
                        timeType=timeType, startTime=startTime,
                        endTime=endTime, timeout=timeout)
  except Exception as ex:
    msg = 'Error when querying evrs from GlobalLad'
    logger.error(traceback.format_exc())
    raise Exception(msg) from ex

  logger.info("Found %d EVR results from GlobalLad." %(len(evrs)))

  # convert data to format required by server spec
  evr_dicts = []

  for evr in evrs:
    evr_dict = get_evr_dict(sessionId=int(evr['sessionNumber']),
                  eventId=int(evr['evrId']),
                  vcId=(int(evr['vcid']) if (evr['vcid'] != "") else None),
                  evrName=str(evr['evrName']),
                  evrLevel=str(evr['evrLevel']),
                  fromSSE=(not str2bool(evr['isFsw'])),
                  evrMessage=str(evr['message']),
                  evrModule=None,
                  sclk=str(evr['sclk']),
                  ert=doyToIsoZ(normalize_with_microsecs(evr['ert'])),
                  scet=doyToIsoZ(normalize_with_microsecs(evr['scet'])),
                  isRecorded=(not str2bool(evr['isRealTime'])))
    evr_dicts.append(evr_dict)
  return evr_dicts

def get_chill_evr(sessionId: int, evrTypes: List[EVRType]=None, evrName: str=None, eventId: int=None,
              evrLevel: str=None, evrModule: str=None, timeType: TimeType=None,
              startTime: str=None, endTime: str=None, timeout: int=None) -> List[Dict]:
  '''
  Dispatches chill_get_evr command, validates output, and generates response
  based on spec for evr response.
  Time format for all time types except SCLK (in GMT) is YYYY-DOYThh:mm:ss.ttt

  Parameters
  ------------------
  sessionId:
    AMPCS session id
  evrTypes: 
    list of evr types to query. Example: [EVRType.FSW_REALTIME,EVRType.SSE]
  evrName:
    name or name pattern of evrs to match. Use % for wildcard.
  eventId:
    EVR event ID
  evrLevel:
    EVR level
  evrModule:
    EVR module
  timeType:
    Should be one of TimeType
  startTime:
    Begin time of query range
  endTime:
    End time of query range
  timeout:
    Time to wait in seconds before returning timeout


  Returns:
  List[Dict]
    list of evrs in dict

  '''
  evrs = []

  try:
    if (timeType == TimeType.ERT or timeType == TimeType.SCET):
      if (startTime is not None):
        datetime.strptime(startTime, '%Y-%jT%H:%M:%S')
      if (endTime is not None):
        datetime.strptime(endTime, '%Y-%jT%H:%M:%S')
  except ValueError as ex:
    msg = 'Expected DOY format with integer seconds - ex:2017-310T19:27:13'
    logger.exception(msg)
    raise Exception(msg) from ex

  # modify data to what chill_get_evrs cmd accepts
  sessionId_str = None
  if sessionId is not None:
      sessionId_str = str(sessionId)

  tt = None
  if timeType is not None:
    tt = timeType.value

  evrtypes_str = None
  if evrTypes != [] and evrTypes is not None:
    evrtypes_str = ''
    for etype in evrTypes:
      evrtypes_str = evrtypes_str + etype.value

  eventid_str = None
  if eventId is not None:
      eventid_str = str(eventId)

  try:

    # create subprocess and send cmd
    evrs_str = chill_query.chill_get_evr(sessionId_str, evrtypes_str, evrName,
                          eventid_str, evrLevel, evrModule, tt,
                          startTime, endTime, timeout)

  except subprocess.TimeoutExpired as ex:
    # return empty response for timeout
    msg = 'Timeout expired while running chill_get_evrs'
    logger.exception(msg)
    raise Exception(msg) from ex

  except subprocess.CalledProcessError as ex:
    # return empty response for error
    msg = 'Error while running chill_get_evrs'
    logger.exception(msg)
    raise Exception(msg) from ex

  # return empty response if nothing was found
  if evrs_str == '':
    return evrs

  # parse csv output otherwise
  reader = get_csv_row_reader(evrs_str)

  for row in reader:
    # capture every column as string, and cast
    # it appropriately as per spec definition
    evr = get_evr_dict(
      sessionId=int(row[1]),
      eventId=int(row[6]),
      vcId=(int(row[7]) if (row[7] != '') else None),
      evrName=row[3],
      evrLevel=row[5],
      fromSSE=str2bool(row[9]),
      evrMessage=row[15],
      evrModule=row[4],
      sclk=row[11],
      ert=doyToIsoZ(normalize_with_microsecs(row[13])),
      scet=doyToIsoZ(normalize_with_microsecs(row[12])),
      isRecorded= not str2bool(row[10])
    )
    evrs.append(evr)
      
  logger.info(f'Found {len(evrs)} EVR results from CHILL.')

  return evrs

def get_chill_evr_multi(sessionId: int, evrTypes: List[EVRType]=[], evrNames: List[str]=[], eventIds: List[int]=[],
              evrLevels: List[str]=[], evrModules: List[str]=[], timeType: TimeType=None,
              startTime: str=None, endTime: str=None, timeout: int=None) -> List[Dict]:
  '''
  Queries for EVR using chill_get_evrs. More than one EVR name can be queried.
  Time format for all time types except SCLK (in GMT) is YYYY-DOYThh:mm:ss.ttt

  Parameters
  ------------------
  sessionId:
    AMPCS session id
  evrTypes:
    list of evr types to query. Example: [EVRType.FSW_REALTIME,EVRType.SSE]
  evrNames:
    names of evrs to match. No wildcard is supported.
  eventIds:
    EVR event ids
  evrLevels:
    EVR levels
  evrModule:
    EVR modules
  timeType:
    Should be one of TimeType
  startTime:
    Begin time of query range
  endTime:
    End time of query range
  timeout:
    Time to wait in seconds before returning timeout

  Returns:
  List[Dict]
    list of evrs in dict

  '''
  evrs = []

  if not isinstance(evrTypes, list):
    msg = f'evrTypes is not a list. evrTypes: {evrTypes}'
    raise Exception(msg)  

  if not isinstance(evrNames, list):
    msg = f'evrNames is not a list. evrNames: {evrNames}'
    raise Exception(msg)
  
  if not isinstance(eventIds, list):
    msg = f'eventIds is not a list. eventIds: {eventIds}'
    raise Exception(msg)
  
  if not isinstance(evrLevels, list):
    msg = f'evrLevels is not a list. evrLevels: {evrLevels}'
    raise Exception(msg)
  
  if not isinstance(evrModules, list):
    msg = f'evrModules is not a list. evrModules: {evrModules}'
    raise Exception(msg)
  
  try:
    if (timeType == TimeType.ERT or timeType == TimeType.SCET):
      if (startTime is not None):
        datetime.strptime(startTime, '%Y-%jT%H:%M:%S')
      if (endTime is not None):
        datetime.strptime(endTime, '%Y-%jT%H:%M:%S')
  except ValueError as ex:
    msg = 'Expected DOY format with integer seconds - ex:2017-310T19:27:13'
    logger.exception(msg)
    raise Exception(msg) from ex

  # modify data to what chill_get_evrs cmd accepts
  sessionId_str = None
  if sessionId is not None:
      sessionId_str = str(sessionId)

  tt = None
  if timeType is not None:
    tt = timeType.value

  evrtypes_str = None
  if len(evrTypes) > 0:
    evrtypes_str = ''
    for etype in evrTypes:
      evrtypes_str = evrtypes_str + etype.value

  try:
    # create subprocess and send cmd
    evrs_str = chill_query.chill_get_evr(sessionId=sessionId_str, evrTypes=evrtypes_str, evrNames=None,
                          eventId=None, evrLevel=None, evrModule=None, timeType=tt,
                          startTime=startTime, endTime=endTime, timeout=timeout)

  except subprocess.TimeoutExpired as ex:
    # return empty response for timeout
    msg = 'Timeout expired while running chill_get_evrs'
    logger.exception(msg)
    raise Exception(msg) from ex

  except subprocess.CalledProcessError as ex:
    # return empty response for error
    msg = 'Error while running chill_get_evrs'
    logger.exception(msg)
    raise Exception(msg) from ex

  # return empty response if nothing was found
  if evrs_str == '':
    return evrs

  # parse csv output otherwise
  reader = get_csv_row_reader(evrs_str)

  for row in reader:
    # capture every column as string, and cast
    # it appropriately as per spec definition
    evr = get_evr_dict(
      sessionId=int(row[1]),
      eventId=int(row[6]),
      vcId=(int(row[7]) if (row[7] != '') else None),
      evrName=row[3],
      evrLevel=row[5],
      fromSSE=str2bool(row[9]),
      evrMessage=row[15],
      evrModule=row[4],
      sclk=row[11],
      ert=doyToIsoZ(normalize_with_microsecs(row[13])),
      scet=doyToIsoZ(normalize_with_microsecs(row[12])),
      isRecorded= not str2bool(row[10])
    )

    if len(evrNames) > 0 and evr.get('evrName') not in evrNames:
      continue
    
    if len(eventIds) > 0 and evr.get('eventId') not in eventIds:
      continue

    if len(evrLevels) > 0 and evr.get('evrLevel') not in evrLevels:
      continue

    if len(evrModules) > 0 and evr.get('evrModule') not in evrModules:
      continue

    evrs.append(evr)
      
  logger.info(f'Found {len(evrs)} EVR results from CHILL.')

  return evrs

def get_eha_dict(sessionId, channelId, dn, eu, vcId, channelName,
              channelType, channelStatus, dnAlarmState, euAlarmState,
              sclk, ert, scet, isRecorded):
  return {
    'sessionId': sessionId,
    'channelId': channelId,
    'dn': dn,
    'eu': eu,
    'vcId': vcId,
    'channelName': channelName,
    'channelType': channelType,
    'channelStatus': channelStatus,
    'dnAlarmState': dnAlarmState,
    'euAlarmState': euAlarmState,
    'sclk': sclk,
    'ert': ert,
    'scet': scet,
    'isRecorded': isRecorded
  }


def get_rt_eha(sessionId: int, timeout: int, channelId: str=None, timeType:TimeType=None, startTime: str=None,
                 endTime: str=None):
  '''
  Dispatches realtime eha query to globallad, validates output, and generates response
  based on spec for eha response

  Keyword arguments:
  sessionId -- single testKey or session Id (int)
  channelId  -- EHA channel ID (string)
  timeType -- Should be one of TimeType enum
  startTime -- Begin time of range (string)
  endTime  -- End time of range (string)
  timeout -- Internal timeout in seconds

  Time format for all time types except SCLK (in GMT) is YYYY-DOYThh:mm:ss.ttt

  Returns:
    list of ehas in dict

  '''
  eha_dicts = []

  try:
    start_dt = datetime.strptime(startTime, '%Y-%jT%H:%M:%S')
    end_dt = datetime.strptime(endTime, '%Y-%jT%H:%M:%S')
  except ValueError as ex:
    msg = 'Expected DOY format with integer seconds - ex:2017-310T19:27:13'
    logger.exception(msg)
    raise Exception(msg) from ex

  if (start_dt > end_dt):
    raise Exception('startTime is after endTime')

  try:
    ehas = lad_query.lad_get_eha(sessionId=sessionId, channelId=channelId,
                        timeType=timeType, startTime=startTime,
                        endTime=endTime, timeout=timeout)
  except Exception as ex:
    msg = 'Error when querying channel values from GlobalLad'
    logger.error(traceback.format_exc())
    raise Exception(msg) from ex

  # convert data to format required by server spec

  for eha in ehas:
    eha_dict = get_eha_dict(sessionId=int(eha['sessionNumber']),
                channelId=str(eha['channelId']),
                dn=str(eha['dn']),
                eu=(float(eha['eu']) if (eha['eu'] != "") else None),
                vcId=(int(eha['vcid']) if (eha['vcid'] != "") else None),
                channelName=None,
                channelType=str(eha['channelType']),
                channelStatus=str(eha['status']),
                dnAlarmState=str(eha['dnAlarmLevel']),
                euAlarmState=str(eha['euAlarmLevel']),
                sclk=str(eha['sclk']),
                ert=doyToIsoZ(normalize_with_microsecs(eha['ert'])),
                scet=doyToIsoZ(normalize_with_microsecs(eha['scet'])),
                isRecorded=(not str2bool(eha['isRealTime'])))
    eha_dicts.append(eha_dict)

  logger.info(f'Got {len(ehas)} EHA results from GlobalLad.')

  return eha_dicts

def get_rt_eha_multi(sessionId: int, timeout: int, channelIds: List[str]=[], timeType:TimeType=None, startTime: str=None,
                 endTime: str=None):
  '''
  Dispatches realtime eha query to globallad, validates output, and generates response
  based on spec for eha response

  Keyword arguments:
  sessionId -- AMPCS session id
  channelId  -- EHA channel ID (string)
  timeType -- Should be one of TimeType enum
  startTime -- Begin time of range (string)
  endTime  -- End time of range (string)
  timeout -- Internal timeout in seconds

  Time format for all time types except SCLK is YYYY-DOYThh:mm:ss.ttt

  Returns:
    list of ehas in dict

  '''
  eha_dicts = []

  try:
    start_dt = datetime.strptime(startTime, '%Y-%jT%H:%M:%S')
    end_dt = datetime.strptime(endTime, '%Y-%jT%H:%M:%S')
  except ValueError as ex:
    msg = 'Expected DOY format with integer seconds - ex:2017-310T19:27:13'
    logger.exception(msg)
    raise Exception(msg) from ex

  if (start_dt > end_dt):
    raise Exception('startTime is after endTime')

  try:
    ehas = lad_query.lad_get_eha_multi(sessionId=sessionId, channelIds=channelIds,
                        timeType=timeType, startTime=startTime,
                        endTime=endTime, timeout=timeout)
  except Exception as ex:
    msg = 'Error when querying channel values from GlobalLad'
    logger.error(traceback.format_exc())
    raise Exception(msg) from ex

  # convert data to format required by server spec

  for eha in ehas:
    eha_dict = get_eha_dict(sessionId=int(eha['sessionNumber']),
                channelId=str(eha['channelId']),
                dn=str(eha['dn']),
                eu=(float(eha['eu']) if (eha['eu'] != "") else None),
                vcId=(int(eha['vcid']) if (eha['vcid'] != "") else None),
                channelName=None,
                channelType=str(eha['channelType']),
                channelStatus=str(eha['status']),
                dnAlarmState=str(eha['dnAlarmLevel']),
                euAlarmState=str(eha['euAlarmLevel']),
                sclk=str(eha['sclk']),
                ert=doyToIsoZ(normalize_with_microsecs(eha['ert'])),
                scet=doyToIsoZ(normalize_with_microsecs(eha['scet'])),
                isRecorded=(not str2bool(eha['isRealTime'])))
    eha_dicts.append(eha_dict)

  logger.info(f'Got {len(ehas)} EHA results from GlobalLad.')

  return eha_dicts

def get_chill_eha(sessionId: int, channelIds: List[str]=[], channelTypes: List[ChannelType]=[],
              timeType:TimeType=None, startTime=None, endTime=None,
              inAlarmFilter:AlarmTypeMap=None, timeout=None):
  '''

  Keyword arguments:
  sessionId -- single testKey or session Id (int)
  channelIds -- list of channel Ids (list of string)
  channelTypes -- list of channel types to read e.g. [ChannelType.FSW_REALTIME,ChannelType.SSE] (list of ChannelType enum)
  timeType -- Type of time  (default = TimeType.ERT) (TimeType enum)
  startTime -- Begin time of range (string)
  endTime  -- End time of range (string)
  inAlarmFilter -- An alarm type (AlarmTypeMap Enum)
  timeout -- Time to wait in seconds before returning timeout (int)

  Time format for all time types except SCLK (in GMT) is YYYY-DOYThh:mm:ss.ttt

  Returns:
  Python dictionary of EhaResponse

 '''

  try:
    if (timeType == TimeType.ERT or timeType == TimeType.SCET):
      if (startTime is not None):
        datetime.strptime(startTime, '%Y-%jT%H:%M:%S')
      if (endTime is not None):
        datetime.strptime(endTime, '%Y-%jT%H:%M:%S')
  except ValueError as ex:
    msg = 'Expected DOY format with integer seconds - ex:2017-310T19:27:13'
    logger.exception(msg)
    raise Exception(msg) from ex

  ehas = []

  # modify data to what chill_get_eha cmd accepts
  sessionId_str = None
  if sessionId is not None:
      sessionId_str = str(sessionId)

  ct = None
  if channelTypes != [] and channelTypes is not None:
    ct = ''
    for ctype in channelTypes:
      ct = ct + ctype.value

  cids = None
  if channelIds != [] and channelIds is not None:
    cids = ','.join(channelIds)

  tt = None
  if timeType is not None:
    tt = timeType.value

  alarm = None
  if inAlarmFilter is not None:
    alarm = inAlarmFilter.value

  try:

    # send cmd
    ehas_str = chill_query.chill_get_eha(sessionId_str, cids, ct, tt,
                          startTime, endTime, alarm, timeout)

    # return empty response if nothing was found
    if ehas_str == '':
      return ehas

  except subprocess.TimeoutExpired as ex:
    logger.exception('Timeout expired while running chill_get_chanvals')
    return ehas

  except subprocess.CalledProcessError as ex:
    logger.exception('Error while running chill_get_chanvals')
    return ehas

  # parse csv output otherwise
  reader = get_csv_row_reader(ehas_str)

  for row in reader:
    # capture every column as string, and cast
    # it appropriately as per spec definition
    eha = get_eha_dict(sessionId=int(row[1]),
                channelId=row[3],
                dn=row[11],
                eu=(float(row[12]) if (row[12] != '') else None),
                vcId=(int(row[5]) if (row[5] != '') else None),
                channelName=row[6],
                channelType=row[17],
                channelStatus=row[13],
                dnAlarmState=row[14],
                euAlarmState=row[15],
                sclk=row[10],
                ert=doyToIsoZ(normalize_with_microsecs(row[8])),
                scet=doyToIsoZ(normalize_with_microsecs(row[9])),
                isRecorded=not str2bool(row[16]))
    ehas.append(eha)

  logger.info(f'Found {len(ehas)} EHA results from CHILL.')

  return ehas

def get_chill_eha_multi(sessionId: int, channelIds: List[str]=[], channelTypes: List[ChannelType]=[],
              timeType:TimeType=None, startTime=None, endTime=None,
              inAlarmFilter:AlarmTypeMap=None, timeout=None):
  '''

  Keyword arguments:
  sessionId -- AMPCS session id
  channelIds -- list of channel Ids (list of string)
  channelTypes -- list of channel types to read e.g. [ChannelType.FSW_REALTIME,ChannelType.SSE] (list of ChannelType enum)
  timeType -- Type of time  (default = TimeType.ERT) (TimeType enum)
  startTime -- Begin time of range (string)
  endTime  -- End time of range (string)
  inAlarmFilter -- An alarm type (AlarmTypeMap Enum)
  timeout -- Time to wait in seconds before returning timeout (int)

  Time format for all time types except SCLK (in GMT) is YYYY-DOYThh:mm:ss.ttt

  Returns:
  Python dictionary of EhaResponse

 '''

  try:
    if (timeType == TimeType.ERT or timeType == TimeType.SCET):
      if (startTime is not None):
        datetime.strptime(startTime, '%Y-%jT%H:%M:%S')
      if (endTime is not None):
        datetime.strptime(endTime, '%Y-%jT%H:%M:%S')
  except ValueError as ex:
    msg = 'Expected DOY format with integer seconds - ex:2017-310T19:27:13'
    logger.exception(msg)
    raise Exception(msg) from ex

  ehas = []

  # modify data to what chill_get_eha cmd accepts
  sessionId_str = None
  if sessionId is not None:
      sessionId_str = str(sessionId)
  
  ct = None
  if channelTypes != [] and channelTypes is not None:
    ct = ''
    for ctype in channelTypes:
      ct = ct + ctype.value

  cids = None
  if channelIds != [] and channelIds is not None:
    cids = ','.join(channelIds)

  tt = None
  if timeType is not None:
    tt = timeType.value

  alarm = None
  if inAlarmFilter is not None:
    alarm = inAlarmFilter.value

  try:

    # send cmd
    ehas_str = chill_query.chill_get_eha(sessionId_str, cids, ct, tt,
                          startTime, endTime, alarm, timeout)

    # return empty response if nothing was found
    if ehas_str == '':
      return ehas

  except subprocess.TimeoutExpired as ex:
    logger.exception('Timeout expired while running chill_get_chanvals')
    return ehas

  except subprocess.CalledProcessError as ex:
    logger.exception('Error while running chill_get_chanvals')
    return ehas

  # parse csv output otherwise
  reader = get_csv_row_reader(ehas_str)

  for row in reader:
    # capture every column as string, and cast
    # it appropriately as per spec definition
    eha = get_eha_dict(sessionId=int(row[1]),
                channelId=row[3],
                dn=row[11],
                eu=(float(row[12]) if (row[12] != '') else None),
                vcId=(int(row[5]) if (row[5] != '') else None),
                channelName=row[6],
                channelType=row[17],
                channelStatus=row[13],
                dnAlarmState=row[14],
                euAlarmState=row[15],
                sclk=row[10],
                ert=doyToIsoZ(normalize_with_microsecs(row[8])),
                scet=doyToIsoZ(normalize_with_microsecs(row[9])),
                isRecorded=not str2bool(row[16]))
    ehas.append(eha)

  logger.info(f'Found {len(ehas)} EHA results from CHILL.')

  return ehas

def get_dp_dict(sessionId, vcId, dpStatus, apId,
            apIdProductType, filepath, filesize, creationTime,
            sclk, ert, scet):
  checkSessionId(sessionId)

  return {
    "sessionId":sessionId,
    "vcId":vcId,
    "dpStatus":dpStatus,
    "apId":apId,
    "apIdProductType":apIdProductType,
    "filePath":filepath,
    "fileSize":filesize,
    "creationTime":creationTime,
    "sclk":sclk,
    "ert":ert,
    "scet":scet
  }

def get_dp (sessionId, dpStatus:DpStatus=None, apIds=None,
            timeType:TimeType=None, startTime=None, endTime=None,
            timeout=None):
  '''

  Keyword arguments:
  sessionId -- single testKey or session Id (int)
  dpStatus -- one of three status enums (DpStatus.ALL,DpStatus.COMPLETE,etc.) (enum)
  apIds -- list of all apIds (each entry must be an int)
  timeType -- Should be one of TimeType enum (enum)
  startTime -- Begin time of range (string)
  endTime  -- End time of range (string)
  timeout -- timeout in seconds

  Time format for all time types except SCLK (in GMT) is YYYY-DOYThh:mm:ss.ttt

  Returns:
  list data product in dict

  '''

  try:
    if (timeType == TimeType.ERT or timeType == TimeType.SCET):
      if (startTime is not None):
        datetime.strptime(startTime, '%Y-%jT%H:%M:%S')
      if (endTime is not None):
        datetime.strptime(endTime, '%Y-%jT%H:%M:%S')
  except ValueError as ex:
    msg = "Expected DOY format with integer seconds - ex:2017-310T19:27:13"
    logger.exception(msg)
    raise Exception(msg) from ex

  dps = []

  # modify data to what chill_get_products accepts
  apids = None
  if (apIds != [] and apIds is not None):
    apids = ','.join(str(x) for x in apIds)

  tt = None
  if timeType is not None:
    tt = timeType.value

  dpstat = None
  if (dpStatus is not None):
    dpstat = dpStatus.value

  try:
    # send cmd
    dps_str = chill_query.chill_get_dp (str(sessionId), dpstat, apids,
                        tt, startTime,endTime,timeout)

  except subprocess.TimeoutExpired as ex:
    msg = 'Timeout expired while running chill_get_products'
    logger.exception(msg)
    raise Exception(msg) from ex

  except subprocess.CalledProcessError as ex:
    msg = 'Error while running chill_get_products'
    logger.exception(msg)
    raise Exception(msg) from ex

  # return empty response if nothing was found
  if (dps_str == ''):
    return []

  # parse csv output otherwise
  reader = get_csv_row_reader(dps_str)

  for row in reader:
    # capture every column as string, and cast
    # it appropriately as per spec definition
    # TODO: unsure about dpStatus and dpName (not in csv_config output)
    dp = get_dp_dict(
      sessionId=int(row[1]),
      vcId=int(row[3]),
      dpStatus=row[20],
      apId=int(row[4]),
      apIdProductType=row[5],
      filepath=row[10],
      filesize=float(row[18]),
      creationTime=row[6],
      sclk=row[9],
      ert=doyToIsoZ(normalize_with_microsecs(row[8])),
      scet=doyToIsoZ(normalize_with_microsecs(row[7]))
    )
    dps.append(dp)

  logger.info(f'Found {len(dps)} data product results from CHILL.')

  return dps

def get_current_datetime_stamp():

  # get current time
  now_time = datetime.now()
  formatted_time = now_time.strftime('%Y-%m-%dT%H%M%S')

  return formatted_time

def create_temp_dir_and_logfiles():

  # see if /tmp/cs exists, if not make the base path
  if os.path.isdir(CUSTOM_SCRIPT_LOG_PATH_BASE) is False:
    # open permissions on the base dir so that multiple application users can read/write to it/make tars
    os.makedirs(CUSTOM_SCRIPT_LOG_PATH_BASE)    
    os.chmod(CUSTOM_SCRIPT_LOG_PATH_BASE, stat.S_IRWXO | stat.S_IRWXG | stat.S_IRWXU)

  # create a unique session (script) id. This is the script_run_id
  script_run_id = str(uuid.uuid4())
  # get current time
  formatted_time = get_current_datetime_stamp()

  datetime_script_run_id = f'{formatted_time}-{script_run_id}'

  # example path: "/tmp/cs/datetime-uuid/"
  subfolder_with_datetime_and_uuid = os.path.join(CUSTOM_SCRIPT_LOG_PATH_BASE, datetime_script_run_id)
  logger.debug(f'Subfolder with datetime stamp and ID: {subfolder_with_datetime_and_uuid}')

  # dir doesn't exists so create it 
  os.makedirs(subfolder_with_datetime_and_uuid)

  return subfolder_with_datetime_and_uuid, script_run_id

def tar_custom_script_log_files(temp_dir, script_run_id):

  '''
  This function will create a tar package of the input.json, output.json, and script.log files. 
  Each tar will be datestamped with the time the tar was created and the uuid. 

  example tar created in the script temp dir: `/tmp/cs/uuid.tar.gz`

  '''
  tar_full_path = os.path.join(CUSTOM_SCRIPT_LOG_PATH_BASE, script_run_id + '.tar.gz')
  logger.debug(f'Full tar path: {tar_full_path}') 

  with tarfile.open(tar_full_path, 'w:gz') as tar_handle:
    for file_name in glob.glob(os.path.join(temp_dir, '*')):
        isolated_file_name = os.path.basename(file_name)
        logger.debug(f'File found in temp dir: {isolated_file_name}')
        logger.debug(f'Storing in tar: {os.path.join(script_run_id, isolated_file_name)}')
        tar_handle.add(file_name, arcname=os.path.join(script_run_id, isolated_file_name))

  return tar_full_path


def initialize_input_output_and_log_files(subdir, inputs, outputs, script_run_id):

  # create input file 
  input_file_path = os.path.join(subdir, 'input.json')

  with open(input_file_path, 'w') as infile:
    json.dump(inputs, infile)

  # create output file
  output_file_path = os.path.join(subdir, 'output.json')

  with open(output_file_path, 'w') as outfile:
    json.dump(outputs, outfile)

  # create main log file
  script_log_file_path = os.path.join(subdir, 'script.log')

  # logfile_url produces url in convention: "custom_scripts/<script_run_id>/files"
  logfile_url = '/'.join(['custom_script', script_run_id, 'files'])

  return input_file_path, output_file_path, script_log_file_path, logfile_url

def launch_script(path_to_script, inputs, outputs):
  
  # create the temp dir for the custom script files, returns the temp dir and the uuid (to be used later)
  custom_script_temp_dir, script_run_id= create_temp_dir_and_logfiles()
  input_file_path, output_file_path, script_log_file_path, logfile_url = \
    initialize_input_output_and_log_files(custom_script_temp_dir, inputs, outputs, script_run_id)

  logger.debug(f'Input file: {input_file_path}')
  logger.debug(f'Output file: {output_file_path}')
  logger.debug(f'Log file: {script_log_file_path}')
  logger.debug(f'Script run id: {script_run_id}')
  logger.debug(f'Logfile url: {logfile_url}')

  # open a script log file with no buffering
  # Python2:
  #     buffering=0 is available regardless of text or binary file
  # Python3:
  #     buffering=0 is available only for binary file 
  # 
  # Note that script_log_file_path file is opened in binary mode to be compatible with Python2 and Python3.
  # In Python3, since the file is opened as binary, if stdout.write('abc') is used in the sub-process, 
  # it would give a TypeError: a bytes-like object is required, not 'str',
  # But since the file is used for redirection of stdout/stderr, it seems to work fine for Python3.
  log_file = open(script_log_file_path, 'wb', buffering=0)
  
  # disable buffering of stdout/stderr of the subprocess by setting PYTHONUNBUFFERED
  script_env = os.environ.copy()
  script_env['PYTHONUNBUFFERED'] = 'YES'  
 
  process = subprocess.Popen([path_to_script, input_file_path, output_file_path], 
    preexec_fn=os.setsid, env=script_env, stdout=log_file, stderr=log_file)
  process_pid = process.pid

  r = redis.StrictRedis(host='localhost', port=6379, db=0)

  process_redis_data = {
    'process_id': str(process_pid),
    'output_path': output_file_path,
    'logfile_path': script_log_file_path,
    'logfile_url': logfile_url,
    'custom_script_temp_dir': custom_script_temp_dir
  }

  logger.debug(f'Stored redis data: {process_redis_data}')
  r.set(str(script_run_id), json.dumps(process_redis_data))

  return script_run_id


def get_script_log_lines(log_file_path):

  log_lines_list = []

  last_lines = tailer.tail(open(log_file_path), 25)

  for l in last_lines:
    # remove the pesky "/n" at the end of each log line
    log_lines_list.append(l.rstrip('\n'))
  
  return log_lines_list


def check_script_hash(joined_path, script_hash):

  valid_hash = False

  # check hash. return error if hashes do not match 
  BLOCK_SIZE = 65536
  generated_hash = hashlib.sha256()
  with open(joined_path, 'rb') as f:
    fb = f.read(BLOCK_SIZE) # Read from the file. Take in the amount declared above
    while len(fb) > 0: # While there is still data being read from the file
        generated_hash.update(fb) # Update the hash
        fb = f.read(BLOCK_SIZE) # Read the next block from the file

  if generated_hash.hexdigest() == script_hash:
    valid_hash = True

  return valid_hash, script_hash, generated_hash.hexdigest()

def start_custom_script(script_hash, script_path, inputs, outputs): 

  logger.info(f'Starting custom script: {script_path}')

  # join absolute and relative paths together 
  # absolute path needs to be sourced from environment variable set on the config file
  base_path = _custom_script_base_dir
  relative_path_to_base_path = script_path
  raw_joined_path = os.path.join(base_path, relative_path_to_base_path)
  joined_path = os.path.normpath(raw_joined_path)
  logger.debug(f'Joined custom scripts path: {joined_path}')

  # if file does not exist return error 
  if os.path.isfile(joined_path) is False:
    raise Exception(f'Custom script cannot be found: {joined_path}')
  
  # check hash
  try: 
    valid_hash, script_hash, generated_hash = check_script_hash(joined_path, script_hash)
  except Exception as ex:
    raise Exception(f'Failed to check script hash') from ex

  if valid_hash is False:
    msg = f'File hash input ({script_hash}) did not match the file hash: {generated_hash}'
    raise Exception(msg)
  else:
    msg = "File hash matches generated file hash"
    logger.debug(msg)
  
  try:
    script_run_id = launch_script(joined_path, inputs, outputs)
  except Exception as ex:
    raise Exception(f'Failed to launch script') from ex
  
  logger.debug(f'Script ID generated: {script_run_id}')

  return {'scriptRunId': script_run_id}


def construct_script_outputs(output_json):

  logger.debug(f'Output json: {output_json}')

  structure = {}

  if output_json.get('inputs'):
    structure['inputs'] = output_json['inputs']

  # parse output - object
  if output_json.get('outputs'):
    structure['outputs'] = output_json['outputs']

  # parse output_array - list
  if output_json.get('output_array'):
    structure['output_array'] = output_json['output_array']

  # cycle through entries and extract entry_outputs and entry_output_array
  if output_json.get('entries'):

    structure['entries'] = []
    for entry in output_json['entries']:
      entry_structure = {}
      
      entry_structure['verification_status'] = entry.get('verification_status')

      if entry.get('entry_inputs'):
        entry_structure['entry_inputs'] = entry['entry_inputs']

      if entry.get('entry_output_array'):
        entry_structure['entry_output_array'] = entry['entry_output_array']
      
      if entry.get('entry_outputs'):
        entry_structure['entry_outputs'] = entry['entry_outputs']

      structure['entries'].append(entry_structure)

  return structure

def get_script_status_dict(outputs, script_status, logfile_path, logfile_lines, logfile_url):
  return {
      "custom_script_outputs": outputs,
      "custom_script_status": script_status,
      "logfile_path": logfile_path,
      "logfile_lines": logfile_lines,
      "logfile_url": logfile_url
  }

def get_custom_script_status(script_run_id):

  logger.debug(f'Getting the custom script status for script_run_id: {script_run_id}')

  # get script information via script ID from Redis
  r = redis.StrictRedis(host='localhost', port=6379, db=0)

  try:
    script_info_redis = json.loads(r.get(script_run_id))
  except Exception as ex:
    msg = f'The script run id ({script_run_id}) was not found in REDIS records. Exception: {ex}'
    logger.error(msg)
    raise Exception(msg)

  logger.debug(f'SCRIPT_INFO FROM REDIS: {script_info_redis}')

  # extract PID and see if it's still running 
  pid = script_info_redis.get('process_id') 
  logfile_path = script_info_redis.get('logfile_path')
  output_dir = script_info_redis.get('output_path')
  logfile_url = script_info_redis.get('logfile_url')

  if pid is None:
    msg = f'PID could not be found for script run id ({script_run_id}) in Redis. Check the logs: {logfile_path}'
    logger.error(msg)
    raise Exception(msg)

  # use os.kill to figure out if pid is still running
  pid_is_alive = None

  # preserve current method of checking if pid exists (which means the CS process is still running)
  try:
    os.kill(int(pid), 0)
  except OSError:
    # if the process does not exist, the CS process has ended nominally
    pid_is_alive = False
    logger.debug(f'PID: {pid} is DEAD')
  else:
    # if the process still exists we need to branch the logic to determine if the pid is a zombie process or if it is truly still running
    p = psutil.Process(int(pid))
    # useful pid process status logging
    pid_status_msg = f'PID status: {p.status()}'
    logger.debug(pid_status_msg)
    if p.status() == psutil.STATUS_ZOMBIE:
      msg = f'pid: {pid} is a defunct process'
      logger.debug(msg)
      pid_is_alive = False
    else:
      pid_is_alive = True    

  # extract outputs from outputs dir
  try:
    output_json = _load_json_with_retry(output_dir, 10, 0.1)
  except Exception as ex:
    msg = f'Error when parsing the script output file. Error: {ex}'
    logger.error(msg)
    raise Exception(msg)

  logger.debug(f'Output file content: {output_json}')

  # extract script status & outputs from output json 
  script_status = output_json.get('custom_script_status')
  if script_status is None:
    msg = 'custom_script_status field was not found in the output file'
    logger.error(msg)
    raise Exception(msg)
  
  # construct script outputs to be sent back to venue server
  constructed_output_json = construct_script_outputs(output_json)
  
  # extract the log file lines
  logfile_lines = get_script_log_lines(logfile_path)

  # this means that the process is dead
  if script_status == 'PENDING' and pid_is_alive is False:
    script_status = 'ERROR'
    output_json['custom_script_status'] = 'ERROR'

    # need to write to output file so that PENDING CAN BE CHANGED TO ERROR  
    with open(output_dir, 'w') as outfile:
      logger.warning(f'The script exited without setting script_status. Write to output file: {outfile}')
      json.dump(output_json, outfile)

  return get_script_status_dict(constructed_output_json, script_status, logfile_path, logfile_lines, logfile_url)


def halt_custom_script(script_run_id):

  logger.debug(f'Halting custom script for script_run_id: {script_run_id}')

  # get script information via script ID from Redis 
  r = redis.StrictRedis(host='localhost', port=6379, db=0)
  try:
    script_info_redis = json.loads(r.get(script_run_id))
  except Exception as ex:
    msg = f'The script run id (script_run_id) was not found. Cannot halt script: {ex}'
    logger.error(msg)
    raise Exception(msg)

  pid = script_info_redis.get('process_id')

  if pid is None:
    msg = f'PID: {script_run_id} could not be found in Redis'
    logger.error(msg)
    raise Exception(msg)
  else:
    pid = int(pid)

  try:
    os.kill(pid, 0)
  except OSError:
    logger.warning(f'Error when killing a custom script (PID: {pid}). It may have already exited.')
  else:
    logger.debug(f'PID: {pid} was alive, halted main process and children processes...')


  # if the process group doesn't exist, it needs to exit gracefully
  try:
    os.killpg(os.getpgid(pid), signal.SIGTERM)
  except:
    logger.warning(f'Error when killing process group for pid: {pid}. The process may not exist any more.')

  # delete script (session) id from Redis (keep Redis clean)
  r.delete(script_run_id)

  return ''

def get_custom_script_files(script_run_id):

  logger.debug(f'Retrieving latest custom script logs and package them into tarball: {script_run_id}')

  #custom_script_temp_dir = os.path.join(CUSTOM_SCRIPT_LOG_PATH_BASE, script_run_id)

  # get script information via script ID from Redis
  r = redis.StrictRedis(host="localhost", port=6379, db=0)

  try:
    script_info_redis = json.loads(r.get(script_run_id))
  except Exception as ex:
    msg = f'The script run id ({script_run_id}) was not found. Error: {ex}'
    logger.error(msg)
    raise Exception(msg)

  logger.debug(f'SCRIPT_INFO FROM REDIS: {script_info_redis}')

  custom_script_temp_dir = script_info_redis.get('custom_script_temp_dir')

  # check if base dir + datetime stamp exists, else return error
  # ex: "/tmp/cs/timestamp-uuid"
  if os.path.exists(custom_script_temp_dir) is False:
    msg = f'Custom script temp dir ({custom_script_temp_dir}) was not found'
    logger.error(msg)
    raise Exception(msg)
  
  try:
    tar_path = tar_custom_script_log_files(temp_dir=custom_script_temp_dir, script_run_id=script_run_id)
    logger.debug(f'Full tar path: {tar_path}')
  except Exception as ex:
    msg = f'There was an error packaging the custom script logs into a tarball: {ex}'
    logger.error(msg)
    raise Exception(msg)

  return tar_path



def decode_1553(start_time, end_time, time_type, duration, variables, username):
  logger.debug(f'decode_1553 start_time: {start_time} end_time: {end_time} time_type: {time_type} duration: {duration} variables: {variables} username: {username}')
  # Error Catch: There needs to be a time type associated with the start and end times provided. 
  if start_time or end_time:
    if time_type is None:
      raise Exception('Time input must include a time type.')

  # Error Catch: There needs to be variables to query for the 1553 parser. 
  if variables == None:
    msg = 'No bus variable names were provided.'
    logger.error(msg)
    raise Exception(msg)

  # Validate that times are nominal for operations ahead.
  try:
    parsed_start_time, parsed_end_time = return_validated_start_end_times(start_time, end_time, time_type, duration)
  except TimeParsingError as ex:
    msg = f'Error when parsing start and end times. ex: {ex}'
    logger.error(msg)
    raise Exception(msg) from ex

  # TODO: these are not used??
  # 1553 Parser will make use of SCLK time if time type is SCLK. 
  # These two variables will indicate whether the parser will filter on SCLK values.
  if time_type == 'SCLK':
    sclk_start_time = parsed_start_time
    sclk_end_time = parsed_end_time
  else:
    sclk_start_time = None 
    sclk_end_time = None

  # TODO: not used??
  default_timeout_sec = 60
  filters = []
  date_search_dict_str = {}
  lookback_days = 60 #excludes current day
  date_search_dict_str = doys_for_lookback(lookback_days)

  sess_name = '*' 
  side_str = '*'

  path_tmpl = _bus_1553_logfile_path

  # fill in path vars in 1553 dictionary
  dict_location = get_dict_path(_logfile_1553_dictionary_file_path, side_str, sess_name, username)

  try:
    logfile_paths = get_most_recent_1553_logfiles(path_template=path_tmpl,
                                                  side_str=side_str,
                                                  sess_name=sess_name, 
                                                  username=username,
                                                  start_time=parsed_start_time,
                                                  end_time=parsed_end_time)      

  except TimeoutError as ex:
    msg = 'Timeout expired while querying for 1553 Bus log'
    logger.exception(msg)
    raise Exception(msg) from ex

  except subprocess.CalledProcessError as ex:
    msg = 'Error when querying for 1553 Bus log'
    logger.exception(msg)
    raise Exception(msg) from ex

  logger.info(f'LOGFILES RETURNED: {logfile_paths}')

  if len(logfile_paths) == 0:
    msg = f'No 1553 log files were found for the specified time range. Start time: {start_time} and End time: {end_time}'
    logger.error(msg)
    raise Exception(msg)

  if _irig_source.lower() == 'true':
    assumed_year = get_assumed_year(logfile_paths[0])
  else:
    assumed_year = None 
  
  logger.debug(f'irig source: {_irig_source}')
  logger.debug(f'Assumed year: {assumed_year}')
  # information needed to run decoder and return appropriate information
  essential_info = {
    'assumed_year': assumed_year, 
    'logfile': logfile_paths,
    'irig_status': _irig_source,
    'dictionary': dict_location,
    'time_type': time_type,
    'variables': variables, 
    'query_start_time': parsed_start_time if time_type == 'SCET' else None,
    'query_end_time': parsed_end_time if time_type == 'SCET' else None,
    'sclk_start': parsed_start_time if time_type == 'SCLK' else None,
    'sclk_end': parsed_end_time if time_type == 'SCLK' else None
  }

  logger.debug(f'essential info object: {essential_info}')

  try:
    parsed_list = decode_1553_log_files(essential_info, _logfile_1553_dictionary_file_path)
  except bitstring.InterpretError as ex:
    msg = 'Error when decoding 1553 Bus log'
    logger.exception(msg)
    raise Exception(msg) from ex
  except Exception as ex:
    msg = 'Error when decoding 1553 Bus log'
    logger.exception(msg)
    raise Exception(msg) from ex
  
  logger.debug(f'Number of 1553 log entries found: {len(parsed_list)}')
    
  return parsed_list

