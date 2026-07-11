#!/bin/bash
##
## Copyright (c) 2024 Numurus, LLC <https://www.numurus.com>.
##
## This file is part of nepi-engine
## (see https://github.com/nepi-engine).
##
## License: 3-clause BSD, see https://opensource.org/licenses/BSD-3-Clause
##

#######################################################################################################
# deploy_nepi_scripts.sh [script.py ...]
#
# Deploys NEPI automation scripts to the scripts folder on the target, where
# scripts_mgr discovers them within a second (no build, no restart needed):
#
#     /mnt/nepi_storage/nepi_scripts/
#
# With no arguments it deploys ALL *.py files sitting next to this script;
# pass filenames to deploy a subset:
#     ./deploy_nepi_scripts.sh my_script_node.py
#
# No chmod or line-ending fixes needed here: scripts_mgr chmods scripts on
# launch and runs dos2unix on every new/changed file it sees.
#
# The script requires the following environment variable be set
#    NEPI_REMOTE_SETUP: Indicates whether running from development host or directly on target
#                      (1 = Dev. Host, 0 = From Target)
# In the case that NEPI_REMOTE_SETUP == 1, some further environment variables must be set
#    NEPI_TARGET_IP: Target IP address/hostname
     NEPI_TARGET_IP=${NEPI_IP} #/${NEPI_DEVICE_ID}
#    NEPI_TARGET_USERNAME: Target username
    nepihost=nepi
    if [[ "$NEPI_IN_CONTAINER" -eq 1 ]]; then
      nepihost=nepihost
    fi

     NEPI_TARGET_USERNAME=${nepihost}
#    NEPI_SSH_KEY: Private SSH key for SSH/Rsync to target (as applicable)
     NEPI_SSH_KEY=/home/${USER}/ssh_keys/nepi_engine_default_private_ssh_key
#    NEPI_TARGET_SCRIPTS_DIR: The scripts folder scripts_mgr watches
     NEPI_TARGET_SCRIPTS_DIR=/mnt/nepi_storage/nepi_scripts
#######################################################################################################

REPO_FOLDER=$(cd -P "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)

# Script files from args, or every *.py file next to this script
if [ "$#" -gt 0 ]; then
  SCRIPT_FILES="$@"
else
  SCRIPT_FILES=$(cd "${REPO_FOLDER}" && ls *.py 2>/dev/null)
fi

if [ -z "${SCRIPT_FILES}" ]; then
  echo "No .py files found next to this script"
  exit 1
fi


if [[ -z "${NEPI_REMOTE_SETUP}" ]]; then
  echo "Must have environtment variable NEPI_REMOTE_SETUP set"
  exit 1
fi

if [ "${NEPI_REMOTE_SETUP}" == "0" ]; then
    echo "Running in Local Mode"

elif [ "${NEPI_REMOTE_SETUP}" == "1" ]; then

  if [[ -z "${NEPI_TARGET_IP}" ]]; then
    echo "Remote setup requires env. variable NEPI_TARGET_IP be assigned"
    exit 1
  fi
  if [[ -z "${NEPI_TARGET_USERNAME}" ]]; then
    echo "Remote setup requires env. variable NEPI_TARGET_USERNAME be assigned"
    exit 1
  fi
  if [[ -z "${NEPI_SSH_KEY}" ]]; then
    echo "Remote setup requires env. variable NEPI_SSH_KEY be assigned"
    exit 1
  fi
fi


## Sync update remote clock if needed
echo "Syncing remote clock if needed"
if [ "${NEPI_REMOTE_SETUP}" == "1" ]; then
  sshnhc
fi


for SCRIPT_FILE in ${SCRIPT_FILES}; do

  SCRIPT_SOURCE_PATH=${REPO_FOLDER}/${SCRIPT_FILE}

  if [ ! -f "${SCRIPT_SOURCE_PATH}" ]; then
    echo "Skipping ${SCRIPT_FILE}: file not found: ${SCRIPT_SOURCE_PATH}"
    continue
  fi

  echo "Deploying script ${SCRIPT_FILE} to ${NEPI_TARGET_SCRIPTS_DIR}/"

  if [ "${NEPI_REMOTE_SETUP}" == "0" ]; then
    rsync -avh "${SCRIPT_SOURCE_PATH}" "${NEPI_TARGET_SCRIPTS_DIR}/"

  elif [ "${NEPI_REMOTE_SETUP}" == "1" ]; then
    rsync -avzhe "ssh -i ${NEPI_SSH_KEY} -o StrictHostKeyChecking=no" "${SCRIPT_SOURCE_PATH}" "${NEPI_TARGET_USERNAME}@${NEPI_TARGET_IP}:${NEPI_TARGET_SCRIPTS_DIR}/"

  fi

done
