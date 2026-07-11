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
# TEMPLATE: long-running NEPI automation script (ROS node shape).
#
# Drop this file in /mnt/nepi_storage/nepi_scripts/ on a NEPI device and it
# shows up in the RUI Scripts manager, where it can be launched, stopped,
# monitored (CPU/mem/run counters), and set to auto-start on boot.
#
# scripts_mgr executes this file DIRECTLY (Popen on the file itself), so the
# shebang line above is what selects the interpreter. Keep it.
#
# This shape is a full NEPI node: it connects to ROS through nepi_sdk, exposes
# params/topics under its own namespace, persists settings through the config
# system, and runs until stopped. For a script that does one job and exits,
# use template_script_task.py instead.
#
# TODO: Rename this file (the filename is the script's identity in the
# Scripts manager) and replace every 'script_template' / 'ScriptTemplate'
# token with your own name.

import json

from std_msgs.msg import Bool, String, Float32

from nepi_sdk import nepi_sdk

from nepi_api.node_if import NodeClassIF
from nepi_api.messages_if import MsgIF


#########################################
# Factory Settings
# TODO: Replace with your script's settings. These are only defaults; the
# live values persist through NEPI's config system (set_param + save_config).
#########################################

FACTORY_ENABLED = True
FACTORY_UPDATE_RATE_HZ = 1.0        # how often updaterCb does work

STATUS_PUBLISH_RATE_HZ = 1.0
ERROR_THROTTLE_S = 10.0             # throttle repeated failure warns


#########################################
# Node Class
#########################################

class ScriptTemplateNode(object):

    node_if = None

    enabled = FACTORY_ENABLED
    update_rate_hz = FACTORY_UPDATE_RATE_HZ

    last_error = ""
    update_count = 0

    # The ROS node name. Convention: match the filename without .py
    DEFAULT_NODE_NAME = "script_template_node"

    def __init__(self):
        #### NODE INIT SETUP ####
        # Scripts are standalone processes, so unlike app/driver nodes
        # (launched by rosrun) they must call init_node themselves.
        nepi_sdk.init_node(name=self.DEFAULT_NODE_NAME)
        self.class_name = type(self).__name__
        self.base_namespace = nepi_sdk.get_base_namespace()
        self.node_name = nepi_sdk.get_node_name()
        self.node_namespace = nepi_sdk.get_node_namespace()

        ##############################
        # Create Msg Class
        # MsgIF output goes to the script's log file:
        # /mnt/nepi_storage/logs/nepi_scripts_logs/<this_filename>.log
        self.msg_if = MsgIF(log_name=self.class_name)
        self.msg_if.pub_info("Starting IF Initialization Processes")

        ##############################
        ### Setup Node

        # Configs Config Dict ####################
        self.CFGS_DICT = {
            'init_callback': self.initCb,
            'reset_callback': self.resetCb,
            'factory_reset_callback': self.factoryResetCb,
            'init_configs': True,
            'namespace': self.node_namespace
        }

        # Params Config Dict ####################
        # TODO: One entry per persistent setting.
        self.PARAMS_DICT = {
            'enabled': {
                'namespace': self.node_namespace,
                'factory_val': self.enabled
            },
            'update_rate_hz': {
                'namespace': self.node_namespace,
                'factory_val': self.update_rate_hz
            }
        }

        # Publishers Config Dict ####################
        # Scripts can't define custom msg types (there is no catkin build),
        # so use std_msgs / nepi_interfaces msgs. For structured status the
        # working pattern is JSON in a String msg.
        self.PUBS_DICT = {
            'status_pub': {
                'namespace': self.node_namespace,
                'topic': 'status',
                'msg': String,
                'qsize': 1,
                'latch': True
            }
        }

        # Subscribers Config Dict ####################
        # TODO: One entry per control input.
        self.SUBS_DICT = {
            'set_enabled': {
                'namespace': self.node_namespace,
                'topic': 'set_enabled',
                'msg': Bool,
                'qsize': 10,
                'callback': self.setEnabledCb,
                'callback_args': ()
            },
            'set_update_rate': {
                'namespace': self.node_namespace,
                'topic': 'set_update_rate',
                'msg': Float32,
                'qsize': 10,
                'callback': self.setUpdateRateCb,
                'callback_args': ()
            }
        }

        # Create Node Class ####################
        self.node_if = NodeClassIF(
            configs_dict=self.CFGS_DICT,
            params_dict=self.PARAMS_DICT,
            pubs_dict=self.PUBS_DICT,
            subs_dict=self.SUBS_DICT,
            msg_if=self.msg_if
        )

        self.node_if.wait_for_ready()

        ##############################
        # Load persisted settings over the factory defaults
        self.initCb(do_updates=True)

        # TODO: Do any one-time setup here (connect to devices/apps with
        # nepi_api Connect* classes, open files, start worker threads, ...).

        nepi_sdk.sleep(1)
        # Self-rescheduling oneshot: the next cycle is armed at the end of
        # updaterCb, so cycles never overlap even if one runs long.
        nepi_sdk.start_timer_process(self._update_period(), self.updaterCb, oneshot=True)
        nepi_sdk.start_timer_process(float(1) / STATUS_PUBLISH_RATE_HZ, self.statusPublishCb)

        nepi_sdk.sleep(1)
        self.msg_if.pub_info("Initialization Complete")

        # Stop (RUI Stop button) sends SIGTERM, which triggers a clean ROS
        # shutdown: cleanup_actions runs and spin() returns. A script that
        # doesn't exit within scripts_mgr's stop timeout (10 s) is SIGKILLed.
        nepi_sdk.on_shutdown(self.cleanup_actions)
        nepi_sdk.spin()


    ###################
    ## Main work cycle

    def _update_period(self):
        rate = self.update_rate_hz if (self.update_rate_hz and self.update_rate_hz > 0) else FACTORY_UPDATE_RATE_HZ
        return float(1) / rate

    def updaterCb(self, timer):
        if self.enabled:
            try:
                # TODO: Replace with your script's work: poll a device, fetch
                # from an external service, process data, command other nodes.
                self.update_count += 1
                self.last_error = ""
            except Exception as e:
                self.last_error = str(e)
                self.msg_if.pub_warn("Update cycle failed: " + str(e),
                                     throttle_s=ERROR_THROTTLE_S)
        nepi_sdk.start_timer_process(self._update_period(), self.updaterCb, oneshot=True)


    ###################
    ## Control Callbacks

    def setEnabledCb(self, msg):
        self.msg_if.pub_info(str(msg))
        self.enabled = msg.data
        self.publish_status()
        if self.node_if is not None:
            self.node_if.set_param('enabled', self.enabled)
            self.node_if.save_config()

    def setUpdateRateCb(self, msg):
        self.msg_if.pub_info(str(msg))
        rate = msg.data
        if rate and rate > 0:
            self.update_rate_hz = rate
            self.publish_status()
            if self.node_if is not None:
                self.node_if.set_param('update_rate_hz', self.update_rate_hz)
                self.node_if.save_config()


    #######################
    ### Config Functions

    def initCb(self, do_updates=False):
        if self.node_if is not None:
            self.enabled = self.node_if.get_param('enabled')
            self.update_rate_hz = self.node_if.get_param('update_rate_hz')
        if do_updates:
            pass
        self.publish_status()

    def resetCb(self, do_updates=True):
        self.msg_if.pub_warn("Resetting")
        if do_updates:
            pass
        self.initCb(do_updates=do_updates)

    def factoryResetCb(self, do_updates=True):
        self.msg_if.pub_warn("Factory Resetting")
        if do_updates:
            pass
        self.initCb(do_updates=do_updates)


    ###################
    ## Status Publishers

    def statusPublishCb(self, timer):
        self.publish_status()

    def publish_status(self):
        # TODO: Put everything a consumer (or you, echoing the topic) needs
        # into this dict.
        status = {
            'enabled': bool(self.enabled),
            'update_rate_hz': self.update_rate_hz,
            'update_count': self.update_count,
            'last_error': self.last_error,
        }
        if self.node_if is not None:
            msg = String()
            msg.data = json.dumps(status)
            self.node_if.publish_pub('status_pub', msg)


    #######################
    # Cleanup

    def cleanup_actions(self):
        # Runs on Stop (SIGTERM) and system shutdown. Finish fast: the
        # process has 10 seconds total before scripts_mgr SIGKILLs it.
        # TODO: Stop worker threads, close connections, flush files.
        self.msg_if.pub_info("Shutting down: Executing script cleanup actions")


#########################################
# Main
#########################################
if __name__ == '__main__':
    ScriptTemplateNode()
