#!/usr/bin/env python
#
# Copyright (c) 2024 Numurus <https://www.numurus.com>.
#
# This file is part of nepi applications (nepi_apps) repo
# (see https://https://github.com/nepi-engine/nepi_apps)
#
# License: nepi applications are licensed under the "Numurus Software License",
# which can be found at: <https://numurus.com/wp-content/uploads/Numurus-Software-License-Terms.pdf>
#
# Redistributions in source code must retain this top-level comment bstab.
# Plagiarizing this software to sidestep the license obligations is illegal.
#
# Contact Information:
# ====================
# - mailto:nepi@numurus.com

import time

from nepi_app_pan_tilt_connect.msg import NepiAppPanTiltConnectStatus

from nepi_sdk import nepi_sdk

from nepi_api.node_if import NodeClassIF
from nepi_api.messages_if import MsgIF

from nepi_api.connect_device_if_ptx import ConnectPTXDeviceIF


#########################################
# Control Values
STATUS_PUBLISH_RATE_HZ = 1.0

#########################################
# Node Class
#########################################

# Connect example app: runs a ConnectPTXDeviceIF, which discovers the available
# PTX devices, owns the <node>/ptx_connect connect namespace (ConnectIFStatus
# selector state plus the select_topic subscriber), and connects to the
# selected device. The Nepi_IF_ConnectPTX RUI component talks to that connect
# namespace directly, so this node just keeps the connect interface alive and
# republishes a small connect-oriented status for the app.

class NepiPanTiltConnectApp(object):

    node_if = None
    pt_connect_if = None

    DEFAULT_NODE_NAME = "app_pan_tilt_connect"

    def __init__(self):
        #### APP NODE INIT SETUP ####
        nepi_sdk.init_node(name=self.DEFAULT_NODE_NAME)
        self.class_name = type(self).__name__
        self.base_namespace = nepi_sdk.get_base_namespace()
        self.node_name = nepi_sdk.get_node_name()
        self.node_namespace = nepi_sdk.get_node_namespace()

        ##############################
        # Create Msg Class
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

        # Publishers Config Dict ####################
        self.PUBS_DICT = {
            'status_pub': {
                'namespace': self.node_namespace,
                'topic': 'status',
                'msg': NepiAppPanTiltConnectStatus,
                'qsize': 1,
                'latch': True
            }
        }

        # Create Node Class ####################
        self.node_if = NodeClassIF(
            configs_dict=self.CFGS_DICT,
            pubs_dict=self.PUBS_DICT
        )

        self.node_if.wait_for_ready()

        ##############################
        # Create the PTX connect interface. With no preselected device topic it
        # auto-discovers the available PTX devices and auto-selects one; the RUI
        # overrides the selection by publishing to <node>/ptx_connect/select_topic.
        self.pt_connect_if = ConnectPTXDeviceIF(msg_if=self.msg_if)
        self.pt_connect_if.wait_for_connect_ready()

        ##############################
        self.initCb(do_updates=True)

        time.sleep(1)
        nepi_sdk.start_timer_process(float(1) / STATUS_PUBLISH_RATE_HZ, self.statusPublishCb)

        time.sleep(1)
        self.msg_if.pub_info("Initialization Complete")

        nepi_sdk.on_shutdown(self.cleanup_actions)
        nepi_sdk.spin()


    #######################
    ### Config Functions

    def initCb(self, do_updates=False):
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
        status_msg = NepiAppPanTiltConnectStatus()
        connected = False
        selected_topic = 'None'
        available_topics = []
        if self.pt_connect_if is not None:
            connected = self.pt_connect_if.check_connection()
            selected_topic = self.pt_connect_if.get_selected_topic()
            available_topics = self.pt_connect_if.get_available_topics()
        status_msg.connected = connected
        status_msg.selected_topic = selected_topic
        status_msg.available_topics = available_topics
        if self.node_if is not None:
            self.node_if.publish_pub('status_pub', status_msg)


    #######################
    # Utility Functions
    #######################

    def cleanup_actions(self):
        self.msg_if.pub_info("PAN_TILT_CONNECT: Shutting down: Executing script cleanup actions")
        if self.pt_connect_if is not None:
            self.pt_connect_if.unregister()


#########################################
# Main
#########################################
if __name__ == '__main__':
    NepiPanTiltConnectApp()
