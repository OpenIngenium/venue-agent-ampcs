#!/bin/bash
SCRIPT_FILE=$(realpath $0)
SCRIPT_DIR=$(dirname $SCRIPT_FILE)
VENV_DIR="$SCRIPT_DIR/venv3"

usage() {
  echo "
  Usage: $0 -f ENV_FILE
  
    Options:
      -f ENV_FILE: path to a file that defines environment variables (required)
    Example:
      $0 -f config/venueserver_dev_envs.sh
  "
}

input_error() {
  usage
  exit 1
}

while getopts ":f:" options; do
  case "${options}" in                     
    f)
      ENV_FILE=${OPTARG}
      ;;
    :)
      echo "Error: -${OPTARG} requires a value."
      input_error
      ;;
    *)                                    
      break
      ;;
  esac
done

if [[ -z "$ENV_FILE" ]] 
then
  input_error
fi

echo "ENV_FILE: $ENV_FILE"

if [[ -f "$ENV_FILE" ]]
then
  source "$ENV_FILE"
else
  echo "Error: file not found. $ENV_FILE"
  exit 1
fi


if [[ -z "$ING_MTAK_DIR" ]] 
then
  echo "Error: ING_MTAK_DIR env variable is not defined"  
  exit 1
fi

if [[ -d "$VENV_DIR" ]] 
then
    echo "Use existing Python virtual env: $VENV_DIR"
else
    echo "Creating a Python virtual env: $VENV_DIR"
    python3.9 -m venv $VENV_DIR
fi

AMPCS_REQUIREMENTS="$ING_MTAK_DIR/ampcs_requirements.txt"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

if [[ ! -f "$AMPCS_REQUIREMENTS" ]] 
then
  echo "Error: $AMPCS_REQUIREMENTS file not found"  
  exit 1
fi

if [[ ! -f "$REQUIREMENTS" ]] 
then
  echo "Error: $REQUIREMENTS file not found"  
  exit 1
fi


source $VENV_DIR/bin/activate
python -m pip install -U pip
echo "Installing AMPCS Python dependencies from $AMPCS_REQUIREMENTS"
python -m pip install -r "$AMPCS_REQUIREMENTS"
echo "Installing Python dependencies from $REQUIREMENTS"
python -m pip install -r "$REQUIREMENTS"
# uvicorn requires click version 7 or later
pip install --ignore-installed "click>=7.0.0"

#
# Generate nginx configuration file
export SHORT_HOSTNAME=$(echo $HOSTNAME | cut -d "." -f1)
NGINX_CONF_TEMPLATE=$SCRIPT_DIR/nginx.conf.template
NGINX_CONF=$SCRIPT_DIR/nginx.conf
# replace only specific variables not to break other nginx configuration
envsubst '$HOME $HOSTNAME $SHORT_HOSTNAME $ING_VENUE_DIR' < $NGINX_CONF_TEMPLATE > $NGINX_CONF
echo "NGINX configuration file was generated: $NGINX_CONF"

# Create nginx temp directory
mkdir -p ${HOME}/ingenium/${SHORT_HOSTNAME}/nginx_temp