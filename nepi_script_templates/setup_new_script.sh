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
# setup_new_script.sh
#
# Turns a script template into your own NEPI automation script: renames the
# template file (the filename IS the script's identity in the Scripts manager)
# and, for the node shape, rewrites the class name + DEFAULT_NODE_NAME so they
# line up with the new filename.
#
# Pick a SHAPE:
#   node -> template_script_node.py  ->  <name>_node.py   (long-running ROS node)
#   task -> template_script_task.py  ->  <name>.py        (run-once, exits)
#
# The node shape rewrites the 'script_template' / 'ScriptTemplate' tokens; the
# task shape has no identifiers to rewrite (generic main()/run_task()), so it is
# just renamed. Comments that point at the OTHER template (e.g. "use
# template_script_task.py instead") are left intact.
#
# USAGE
#   1. Copy the template .py you want (and this script + deploy_nepi_scripts.sh)
#      into your own repo/location.
#   2. Edit the EDIT-THESE block below.
#   3. Run it:
#        ./setup_new_script.sh            # rename in place (asks to confirm)
#        ./setup_new_script.sh --dry-run  # just show what it would do
#        ./setup_new_script.sh --yes      # skip the confirmation prompt
#
# After it runs, fill the TODOs, then deploy with ./deploy_nepi_scripts.sh.
#######################################################################################################

# ============================================================================
#  EDIT THESE
# ============================================================================

# REQUIRED. snake_case, the bare script name. Do NOT add "_node" or ".py" --
# the shape suffix is added for you.
#   e.g. SHAPE=node + "battery_monitor" -> battery_monitor_node.py
#        SHAPE=task + "rotate_logs"     -> rotate_logs.py
SCRIPT_NAME="my_script"

# Which template to turn into your script:  node | task
SHAPE="node"

# OPTIONAL (node shape only). PascalCase base for the class -> <base>Node.
# Leave blank to auto-derive from SCRIPT_NAME (battery_monitor -> BatteryMonitor
# -> class BatteryMonitorNode).
CLASS_BASE=""

# ============================================================================
#  ---- no need to edit below here ----
# ============================================================================

set -euo pipefail

usage() {
  cat <<'EOF'
setup_new_script.sh -- turn a NEPI script template into your own script.

Edit the EDIT-THESE block at the top (SCRIPT_NAME, SHAPE, optional CLASS_BASE),
then run:

  ./setup_new_script.sh            rename in place (asks to confirm)
  ./setup_new_script.sh --dry-run  show the plan, change nothing
  ./setup_new_script.sh --yes      skip the confirmation prompt
  ./setup_new_script.sh --help     this text

SHAPE=node  ->  template_script_node.py  ->  <name>_node.py  (rewrites class +
                DEFAULT_NODE_NAME so they match the filename)
SHAPE=task  ->  template_script_task.py  ->  <name>.py       (rename only)
EOF
}

DRY_RUN=0
ASSUME_YES=0
for a in "$@"; do
  case "$a" in
    -n|--dry-run) DRY_RUN=1 ;;
    -y|--yes)     ASSUME_YES=1 ;;
    -h|--help)    usage; exit 0 ;;
    *) echo "Unknown argument: $a"; echo "Try --help"; exit 1 ;;
  esac
done

# ---- Locate ourselves. This script lives NEXT TO the template .py files. ----
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)/$(basename "${BASH_SOURCE[0]}")"
DIR="$(dirname "$SELF")"

# ---- Validate SHAPE -------------------------------------------------------
case "${SHAPE}" in
  node|task) ;;
  *) echo "ERROR: SHAPE must be 'node' or 'task' (got '${SHAPE}')." ; exit 1 ;;
esac

# ---- Validate SCRIPT_NAME -------------------------------------------------
if [ -z "${SCRIPT_NAME}" ] || [ "${SCRIPT_NAME}" = "my_script" ]; then
  echo "ERROR: set SCRIPT_NAME to your script's name first." ; exit 1
fi
if [[ "${SCRIPT_NAME}" == *.py ]]; then
  echo "ERROR: drop the '.py' from SCRIPT_NAME -- it is added for you." ; exit 1
fi
if ! [[ "${SCRIPT_NAME}" =~ ^[a-z][a-z0-9_]*$ ]]; then
  echo "ERROR: SCRIPT_NAME must be snake_case: lowercase letters, digits and"
  echo "       underscores, starting with a letter (e.g. battery_monitor)."
  echo "       Got: '${SCRIPT_NAME}'"
  exit 1
fi
if [ "${SHAPE}" = "node" ] && [[ "${SCRIPT_NAME}" == *_node ]]; then
  echo "ERROR: drop the trailing '_node' from SCRIPT_NAME -- the node shape adds"
  echo "       it for you (you would get '${SCRIPT_NAME}_node.py')."
  exit 1
fi
if [ -n "${CLASS_BASE}" ] && ! [[ "${CLASS_BASE}" =~ ^[A-Za-z][A-Za-z0-9]*$ ]]; then
  echo "ERROR: CLASS_BASE must be PascalCase letters/digits only (e.g. BatteryMonitor)." ; exit 1
fi

# ---- Derive names ---------------------------------------------------------
# PascalCase of the script name: battery_monitor -> BatteryMonitor
PASCAL=""
IFS='_' read -ra _parts <<< "${SCRIPT_NAME}"
for _p in "${_parts[@]}"; do PASCAL+="${_p^}"; done
CLASS_BASE="${CLASS_BASE:-${PASCAL}}"

if [ "${SHAPE}" = "node" ]; then
  SRC="template_script_node.py"
  DST="${SCRIPT_NAME}_node.py"
  CLASS_NAME="${CLASS_BASE}Node"
  NODE_NAME="${SCRIPT_NAME}_node"
else
  SRC="template_script_task.py"
  DST="${SCRIPT_NAME}.py"
fi

SRC_PATH="${DIR}/${SRC}"
DST_PATH="${DIR}/${DST}"

# ---- Show the plan --------------------------------------------------------
echo "======================================================================"
echo " NEPI script template (${SHAPE} shape) -> new script"
echo "======================================================================"
printf "  %-18s %s\n" "file"  "${SRC}  ->  ${DST}"
if [ "${SHAPE}" = "node" ]; then
  printf "  %-18s %s\n" "class"          "ScriptTemplateNode        ->  ${CLASS_NAME}"
  printf "  %-18s %s\n" "DEFAULT_NODE_NAME" "script_template_node   ->  ${NODE_NAME}"
else
  printf "  %-18s %s\n" "(task shape)" "no identifiers to rewrite -- file rename only"
fi
echo "======================================================================"

# ---- Guard rails ----------------------------------------------------------
if [ ! -f "${SRC_PATH}" ]; then
  echo "ERROR: template file not found next to this script:"
  echo "         ${SRC_PATH}"
  echo "       (already renamed, or wrong SHAPE, or not copied here?)"
  exit 1
fi
if [ -e "${DST_PATH}" ]; then
  echo "ERROR: destination already exists: ${DST_PATH}"
  echo "       Pick a different SCRIPT_NAME or remove the existing file."
  exit 1
fi

if [ "${DRY_RUN}" -eq 1 ]; then
  echo "(dry run -- nothing changed)"
  exit 0
fi

if [ "${ASSUME_YES}" -ne 1 ]; then
  read -r -p "Proceed? [y/N] " reply
  case "$reply" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "Aborted."; exit 0 ;;
  esac
fi

# ---- Do it ----------------------------------------------------------------
if [ "${SHAPE}" = "node" ]; then
  # Rewrite ONLY the node's own identifiers. 'template_script' is deliberately
  # left alone: in this file it only appears as a reference to the sibling task
  # template ("use template_script_task.py instead").
  sed -i \
    -e "s/ScriptTemplate/${CLASS_BASE}/g" \
    -e "s/script_template/${SCRIPT_NAME}/g" \
    "${SRC_PATH}"
fi
mv "${SRC_PATH}" "${DST_PATH}"

echo "----------------------------------------------------------------------"
echo " Done: ${DST}"
echo ""
echo " Next:"
echo "   - Keep the shebang line; fill the TODO: markers."
echo "   - Syntax check:"
echo "       python3 -c \"import ast; ast.parse(open('${DST}').read()); print('OK')\""
echo "   - Deploy:  export NEPI_REMOTE_SETUP=0 && ./deploy_nepi_scripts.sh ${DST}"
if [ "${SHAPE}" = "task" ]; then
  echo "   - Note: the other template (template_script_node.py) is untouched;"
  echo "     'deploy_nepi_scripts.sh' with no args deploys EVERY .py here, so"
  echo "     remove any template you are not using before a bulk deploy."
else
  echo "   - Note: the other template (template_script_task.py) is untouched;"
  echo "     'deploy_nepi_scripts.sh' with no args deploys EVERY .py here, so"
  echo "     remove any template you are not using before a bulk deploy."
fi
echo "   - You can delete this setup script now: rm \"${SELF}\""
echo "======================================================================"
