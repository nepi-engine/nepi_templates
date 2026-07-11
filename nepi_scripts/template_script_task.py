#!/usr/bin/env python
#
# Copyright (c) 2024 Numurus <https://www.numurus.com>.
#
# This file is part of nepi engine (nepi_engine) repo
# (see https://github.com/nepi-engine/nepi_engine)
#
# License: NEPI Engine repo source-code and NEPI Images that use this source-code
# are licensed under the "Numurus Software License",
# which can be found at: <https://numurus.com/wp-content/uploads/Numurus-Software-License-Terms.pdf>
#
# Redistributions in source code must retain this top-level comment block.
# Plagiarizing this software to sidestep the license obligations is illegal.
#
# Contact Information:
# ====================
# - mailto:nepi@numurus.com
#
#
# TEMPLATE: run-once NEPI automation script (task shape).
#
# Drop this file in /mnt/nepi_storage/nepi_scripts/ on a NEPI device. Unlike
# template_script_node.py (which runs until stopped), a task script does one
# job and exits. scripts_mgr counts exit code 0 as "completed" and any other
# exit code as "errored out", so return codes are your success/fail report
# in the RUI Scripts manager.
#
# Rules of the road (see SCRIPT_STRUCTURE.md for the full list):
#   * scripts_mgr executes this file DIRECTLY, so the shebang line picks the
#     interpreter. Keep it.
#   * print() output lands in the script's log file at
#     /mnt/nepi_storage/logs/nepi_scripts_logs/<this_filename>.log
#     (unbuffered, so it appears live).
#   * The per-script "cmd line args" config in scripts_mgr is passed to this
#     script as real argv, hence the argparse below.
#   * Stop (RUI Stop button) sends SIGTERM, then SIGKILL 10 seconds later.
#     Handle SIGTERM if you need to clean up or want a graceful abort.
#
# A task script does NOT need ROS. This template is pure Python on purpose:
# most run-once jobs (file shuffling, HTTP calls to external services,
# housekeeping) shouldn't pay the node-startup cost. If your task must talk
# to ROS topics/services, call nepi_sdk.init_node(...) at the start of
# main() and use the nepi_api Connect* classes; everything else here still
# applies.
#
# TODO: Rename this file (the filename is the script's identity in the
# Scripts manager) and fill in run_task().

import argparse
import signal
import sys
import time


# Set by the SIGTERM handler; long loops should check it between steps so a
# Stop from the RUI aborts cleanly instead of getting SIGKILLed at 10 s.
_stop_requested = False


def _handle_sigterm(signum, frame):
    global _stop_requested
    _stop_requested = True
    print("SIGTERM received: finishing current step then stopping")


def run_task(args):
    """Do the actual work. Return 0 on success, non-zero on failure.

    TODO: Replace the body. The loop below just demonstrates progress
    logging and the stop-check pattern.
    """
    print("Task starting: steps=%d, delay=%.1fs" % (args.steps, args.delay))

    for step in range(1, args.steps + 1):
        if _stop_requested:
            print("Stopped early at step %d" % step)
            return 1

        # TODO: One unit of your real work goes here.
        print("Step %d/%d ..." % (step, args.steps))
        time.sleep(args.delay)

    print("Task complete")
    return 0


def main():
    signal.signal(signal.SIGTERM, _handle_sigterm)

    # These arrive from the "cmd line args" field in the script's config
    # (RUI Scripts manager / scripts_mgr script_configs param).
    parser = argparse.ArgumentParser(description="TODO: describe your task")
    parser.add_argument("--steps", type=int, default=5,
                        help="Example arg: number of work steps (default: %(default)s)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Example arg: seconds between steps (default: %(default)s)")
    args = parser.parse_args()

    try:
        return run_task(args)
    except Exception as e:
        # Anything non-zero shows up as an errored run in the Scripts manager.
        print("Task failed: %s" % str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
