#!/usr/bin/env python3

# This is a test custom script which is designed to simulate different
# nominal and off nominal situations.
# 
# It is designed to work with the test suite of the venue-agent

import time
import datetime
import random
import string
import copy
import logging
import sys
import os
from collections import OrderedDict
import json
import statistics

logger = logging.getLogger('test_cs')
formatter = logging.Formatter('[%(levelname)s]:[%(module)s-%(funcName)s]:[%(asctime)s.%(msecs)03dZ] - %(message)s', '%Y-%m-%dT%H:%M:%S')
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(level=logging.DEBUG)
logger.info("Logging Initialized")

class IngeniumStepError(Exception):
    pass

def get_input_output_paths(error_msg):
    """"""
    if len(sys.argv) < 3:
        logger.error(error_msg)
        sys.exit(-1)
    logger.info(sys.argv)
    input_file_abs_path = os.path.abspath(sys.argv[1])
    output_file_abs_path = os.path.abspath(sys.argv[2])

    return (input_file_abs_path, output_file_abs_path)

def read_input_file(input_file_abs_path):
    """"""
    with open(input_file_abs_path) as json_file:
        return json.load(json_file, object_pairs_hook=OrderedDict)

def write_output_file(output_dict, output_file_abs_path):
    """"""
    with open(output_file_abs_path, "w") as outfile:
        json.dump(output_dict, outfile, indent=4)

def random_text(num_chars: int) -> str:
    # You can tailor the charset; here we include letters, digits, punctuation, space
    charset = string.ascii_letters + string.digits + string.punctuation + " "
    return ''.join(random.choice(charset) for _ in range(num_chars))

if __name__ == '__main__':
    
    # Locate the custom script input file
    error_msg = 'USAGE: python test_cs.py input_file_path output_file_path'
    input_file_abs_path, output_file_abs_path = get_input_output_paths(error_msg)
    logger.info(f'input_file_abs_path: {input_file_abs_path}')
    logger.info(f'output_file_abs_path: {output_file_abs_path}')

    # Read the input file
    logger.info('Reading custom script inputs')
    input_dict = read_input_file(input_file_abs_path)

    # Initialize output data
    inputs = copy.deepcopy(input_dict.get('inputs', []))
    variables = input_dict.get('variables', {})
    telemetry= copy.deepcopy(variables.get('telemetry', {}))
    parameters=copy.deepcopy(variables.get('parameters', {}))    
    entries = copy.deepcopy(input_dict.get('entries', {}))

    outputs = {'output_random_data': "",
               'number_of_writes': 0}
    output_array = {}

    output_dict = {
        'custom_script_status': 'PENDING',
        'inputs': inputs,
        'entries': entries,
        'outputs': outputs,
        'output_array': output_array,
        'output_summary': ''
    }

    # Write initial output
    outputs['number_of_writes'] = outputs['number_of_writes'] + 1
    write_output_file(output_dict, output_file_abs_path)
    logger.info('Output file was initialized')


    # If Exception
    if inputs.get('exception_time'):
        exception_time = inputs.get('exception_time')
        time.sleep(exception_time)
        msg = f'Exception generated at time: {exception_time} seconds.'
        logger.error(msg)
        raise IngeniumStepError(msg)


    # Set the output status
    custom_script_status = inputs.get('script_result')

    if inputs.get('output_random_data'):
        outputs['output_random_data'] = random_text(inputs.get('output_random_data'))

    if inputs.get('duration'):
        msg = f"Waiting {inputs.get('duration')} seconds."
        logger.info(msg)

        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(seconds=inputs.get('duration'))

        while end_time > datetime.datetime.now():

            # Heavy writes will continually save cs output (logging save counts and write start/end)
            if inputs.get('heavy_writes') == 'true':
                write_dur = []
                write_start = datetime.datetime.now()
                outputs['number_of_writes'] = outputs['number_of_writes'] + 1
                write_output_file(output_dict, output_file_abs_path)
                write_end = datetime.datetime.now()
                write_duration = (write_end - write_start).total_seconds()
                write_dur.append(write_duration)
                outputs['write_avg_duration'] = statistics.mean(write_dur)
                outputs['write_max_time'] = max(write_dur)
                time.sleep(0.1)


    msg = f'test_cs.py has run to completion with overall status: {custom_script_status}'
    logger.info(msg)
    output_dict['custom_script_status'] = custom_script_status

    text_representation = ""
    
    output_dict['output_summary'] = text_representation

    # Report Final custom_script_status
    outputs['number_of_writes'] = outputs['number_of_writes'] + 1
    write_output_file(output_dict, output_file_abs_path)

