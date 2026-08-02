#!/usr/bin/env python
#
# Copyright (c) 2024 Numurus <https://www.numurus.com>.
#
# This file is part of nepi applications (nepi_drivers) repo
# (see https://https://github.com/nepi-engine/nepi_drivers)
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

##############################################################################
# RBX (Robot) DRIVER TEMPLATE -- NODE
# ---------------------------------------------------------------------------
# Registers an RBXRobotIF -- the widest callback surface of all device types.
# An RBX driver models a controllable vehicle as:
#   - STATES   (e.g. DISARM / ARM)          -> get/setStateInd
#   - MODES    (e.g. STABILIZE / GUIDED..)  -> get/setModeInd
#   - SETUP actions (TAKEOFF, LAUNCH)       -> setSetupActionInd
#   - GO actions                            -> setGoActionInd
#   - goto commands (pose / position / location) for autonomous control
#   - a battery %, a home location, a NavPose, and an AxisControls DOF mask
# You supply an ordered list for each of states/modes/setup_actions/go_actions;
# the IF passes back the selected INDEX into that list.
#
# If the robot's protocol is bridged by a companion node (mavros etc.) launched
# by discovery, this node typically attaches to that node's topics/services.
# Here the hardware calls are stubbed with TODOs.
##############################################################################

import copy

from nepi_sdk import nepi_sdk
from nepi_sdk import nepi_utils
from nepi_sdk import nepi_nav
from nepi_sdk import nepi_settings

from nepi_api.messages_if import MsgIF
from nepi_api.device_if_rbx import RBXRobotIF

from nepi_interfaces.msg import AxisControls

PKG_NAME = 'RBX_TEMPLATE'
FILE_TYPE = 'NODE'


class RbxTemplateNode:

    # ---- Capability tables. The IF returns the INDEX into each list.
    RBX_STATES = ["DISARM", "ARM"]
    RBX_MODES = ["STABILIZE", "LAND", "RTL", "LOITER", "GUIDED"]
    RBX_SETUP_ACTIONS = ["TAKEOFF", "LAUNCH"]
    RBX_GO_ACTIONS = []

    # ---- Runtime-tunable settings.
    CAP_SETTINGS = dict(
        takeoff_height_m={"type": "Float", "name": "takeoff_height_m", "options": ["0.0", "100.0"]},
    )
    FACTORY_SETTINGS = dict(
        takeoff_height_m={"type": "Float", "name": "takeoff_height_m", "value": "10.0"},
    )
    FACTORY_SETTINGS_OVERRIDES = dict()
    settingFunctions = dict(
        takeoff_height_m={'get': 'getTakeoffHeight', 'set': 'setTakeoffHeight'},
    )

    device_info_dict = dict(device_name="", path="", serial_number="",
                            hw_version="", sw_version="")

    POSITION_UPDATE_RATE = 10

    # runtime state
    state_ind = 0
    mode_ind = 0
    battery_percent = 0.0
    takeoff_height_m = 10.0
    takeoff_complete = False
    rbx_if = None
    DEFAULT_NODE_NAME = PKG_NAME.lower() + "_node"

    ##########################################################################
    def __init__(self):
        nepi_sdk.init_node(name=self.DEFAULT_NODE_NAME)
        self.class_name = type(self).__name__
        self.base_namespace = nepi_sdk.get_base_namespace()
        self.node_name = nepi_sdk.get_node_name()
        self.node_namespace = nepi_sdk.get_node_namespace()
        self.msg_if = MsgIF(log_name=self.class_name)
        self.msg_if.pub_info("Starting Node Initialization Processes")

        try:
            self.drv_dict = nepi_sdk.get_param('~drv_dict', dict())
            self.device_name = self.drv_dict['DEVICE_DICT']['device_name']
            self.device_path = self.drv_dict['DEVICE_DICT']['device_path']
            # self.companion_node_name = self.drv_dict['DEVICE_DICT'].get('companion_node_name')
        except Exception as e:
            self.msg_if.pub_warn("Failed to load Device Dict " + str(e))
            nepi_sdk.signal_shutdown(self.node_name + ": no valid Device Dict")
            return

        # ---- If discovery launched a companion protocol node, attach to it:
        #   nepi_sdk.wait_for_node(self.companion_node_name)
        #   ... subscribe to its state/battery/position topics,
        #   ... connect its arm/mode/takeoff services via nepi_sdk.connect_service.
        # TODO: connect to your robot here and confirm the link is up.

        self.navpose_dict = copy.deepcopy(nepi_nav.BLANK_NAVPOSE_DICT)

        # ---- 6-DOF axis capability mask.
        self.axis_controls = AxisControls()
        self.axis_controls.x = True
        self.axis_controls.y = True
        self.axis_controls.z = True
        self.axis_controls.roll = True
        self.axis_controls.pitch = True
        self.axis_controls.yaw = True

        self.cap_settings = self.getCapSettings()
        self.factory_settings = self.getFactorySettings()
        self.device_info_dict["device_name"] = self.device_name
        self.device_info_dict["path"] = self.device_path
        self.device_info_dict["serial_number"] = ""
        self.device_info_dict["hw_version"] = ""
        self.device_info_dict["sw_version"] = ""

        # ---- Register the robot with NEPI.
        self.rbx_if = RBXRobotIF(
            device_info=self.device_info_dict,
            capSettings=self.cap_settings,
            factorySettings=self.factory_settings,
            settingUpdateFunction=self.settingUpdateFunction,
            getSettingsFunction=self.getSettings,
            axisControls=self.axis_controls,
            getBatteryPercentFunction=self.getBatteryPercent,
            states=self.RBX_STATES,
            getStateIndFunction=self.getStateInd,
            setStateIndFunction=self.setStateInd,
            modes=self.RBX_MODES,
            getModeIndFunction=self.getModeInd,
            setModeIndFunction=self.setModeInd,
            checkStopFunction=self.checkStopFunction,
            setup_actions=self.RBX_SETUP_ACTIONS,
            setSetupActionIndFunction=self.setSetupActionInd,
            go_actions=self.RBX_GO_ACTIONS,
            setGoActionIndFunction=self.setGoActionInd,
            # ---- optional autonomous-control callbacks ----
            manualControlsReadyFunction=None,
            autonomousControlsReadyFunction=self.autonomousControlsReady,
            getHomeFunction=self.getHomeLocation,
            setHomeFunction=self.setHomeLocation,
            goHomeFunction=self.goHome,
            goStopFunction=self.goStop,
            gotoPoseFunction=self.gotoPose,
            gotoPositionFunction=self.gotoPosition,
            gotoLocationFunction=self.gotoLocation,
            getNavPoseCb=self.getNavPoseCb,
            navpose_update_rate=self.POSITION_UPDATE_RATE,
            msg_if=self.msg_if,
        )

        nepi_sdk.on_shutdown(self.cleanup_actions)
        self.msg_if.pub_info("Initialization complete")
        nepi_sdk.spin()

    #########################################################################
    # SETTINGS PLUMBING
    #########################################################################
    def getCapSettings(self):
        return self.CAP_SETTINGS

    def getFactorySettings(self):
        settings = self.getSettings()
        for name in settings.keys():
            if name in self.FACTORY_SETTINGS_OVERRIDES:
                settings[name]['value'] = self.FACTORY_SETTINGS_OVERRIDES[name]
        return settings

    def getSettings(self):
        settings = dict()
        for name in self.cap_settings.keys():
            setting = {"name": name, "type": self.cap_settings[name]['type']}
            if name in self.settingFunctions:
                val = getattr(self, self.settingFunctions[name]['get'])()
                if val is not None:
                    setting["value"] = str(val)
                    settings[name] = setting
        return settings

    def settingUpdateFunction(self, setting):
        [name, s_type, data] = nepi_settings.get_data_from_setting(setting)
        if data is None or name not in self.cap_settings:
            return False, self.node_name + " bad/unsupported setting: " + str(setting)
        getattr(self, self.settingFunctions[name]['set'])(data)
        return True, self.node_name + " UPDATED " + str(setting)

    def getTakeoffHeight(self):
        return self.takeoff_height_m

    def setTakeoffHeight(self, val):
        self.takeoff_height_m = float(val)
        return True

    #########################################################################
    # RBX CAPABILITY CALLBACKS  (TODO: implement against your robot/protocol)
    #########################################################################
    def getStateInd(self):
        return self.state_ind

    def setStateInd(self, state_ind):
        # e.g. state_ind 1 == "ARM" -> send arm command to the vehicle.
        if 0 <= state_ind < len(self.RBX_STATES):
            self.state_ind = state_ind
            # TODO: send arm/disarm to hardware.

    def getModeInd(self):
        return self.mode_ind

    def setModeInd(self, mode_ind):
        if 0 <= mode_ind < len(self.RBX_MODES):
            self.mode_ind = mode_ind
            # TODO: command the flight/drive mode on hardware.

    def checkStopFunction(self):
        # Return True if the vehicle should be considered stopped/safe.
        return True

    def getBatteryPercent(self):
        return self.battery_percent

    def setSetupActionInd(self, action_ind):
        # e.g. RBX_SETUP_ACTIONS[action_ind] == "TAKEOFF"
        if 0 <= action_ind < len(self.RBX_SETUP_ACTIONS):
            action = self.RBX_SETUP_ACTIONS[action_ind]
            # TODO: perform the named setup action (takeoff to takeoff_height_m).
            if action == "TAKEOFF":
                self.takeoff_complete = True

    def setGoActionInd(self, action_ind):
        # TODO: perform the named go action (only if RBX_GO_ACTIONS is non-empty).
        pass

    def autonomousControlsReady(self):
        # goto* commands are only honored when this returns True.
        return (self.RBX_STATES[self.state_ind] == "ARM"
                and self.RBX_MODES[self.mode_ind] == "GUIDED"
                and self.takeoff_complete)

    def getHomeLocation(self):
        # TODO: return [lat, lon, alt].
        return [self.navpose_dict['latitude'], self.navpose_dict['longitude'],
                self.navpose_dict['altitude_m']]

    def setHomeLocation(self, geopoint):
        # TODO: command the vehicle's home location.
        pass

    def goHome(self):
        pass    # TODO: command return-to-home

    def goStop(self):
        pass    # TODO: command an immediate stop/hold

    def gotoPose(self, attitude_enu_degs):
        pass    # TODO: command an attitude setpoint (roll,pitch,yaw)

    def gotoPosition(self, point_enu_m, orientation_enu_deg):
        pass    # TODO: command a local ENU position setpoint

    def gotoLocation(self, geopoint_amsl, orientation_ned_deg):
        pass    # TODO: command a global lat/lon/alt setpoint

    def getNavPoseCb(self):
        # TODO: fill from live vehicle telemetry (see npx_template for the dict).
        return copy.deepcopy(self.navpose_dict)

    #########################################################################
    def cleanup_actions(self):
        # TODO: disarm / close links / stop the companion node if this node owns it.
        pass


if __name__ == '__main__':
    node = RbxTemplateNode()
