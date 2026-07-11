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
# PTX (Pan-Tilt) DRIVER TEMPLATE -- NODE
# ---------------------------------------------------------------------------
# Registers a PTXActuatorIF. PTX has the largest callback surface of the
# device types: jog (move + optional timed/speed), absolute goto, position
# feedback, soft limits, speed control, homing, and an optional navpose
# (orientation) report. Pass a callback for every capability the hardware has
# and None for the rest -- PTXActuatorIF advertises only what you wire up.
#
# Angle convention: all angles are DEGREES in the pan-tilt's own frame. Use the
# reverse_*_control flags / direction multipliers to match NEPI's ENU sense.
##############################################################################

import os
import time
import copy
import serial
import serial.tools.list_ports

from nepi_sdk import nepi_sdk
from nepi_sdk import nepi_utils
from nepi_sdk import nepi_nav          # BLANK_NAVPOSE_DICT
from nepi_sdk import nepi_settings

from nepi_api.messages_if import MsgIF
from nepi_api.device_if_ptx import PTXActuatorIF

PKG_NAME = 'PTX_TEMPLATE'
FILE_TYPE = 'NODE'


class PtxTemplateNode:

    # ---- Runtime-tunable settings (see lsx_template for the full pattern).
    CAP_SETTINGS = dict(
        status_update_rate_hz={"type": "Int", "name": "status_update_rate_hz", "options": ["1", "20"]},
    )
    FACTORY_SETTINGS = dict(
        status_update_rate_hz={"type": "Int", "name": "status_update_rate_hz", "value": "5"},
    )
    FACTORY_SETTINGS_OVERRIDES = dict()
    settingFunctions = dict(
        status_update_rate_hz={'get': 'getStatusRate', 'set': 'setStatusRate'},
    )

    # ---- FACTORY_CONTROLS: descriptive keys used by the RUI + the three keys
    #      PTXActuatorIF actually merges (reverse_pan_enabled/reverse_tilt_enabled/
    #      speed_ratio). Extra keys are harmless.
    FACTORY_CONTROLS = dict(
        frame_id='ptx_template_frame',
        pan_joint_name='ptx_template_pan_joint',
        tilt_joint_name='ptx_template_tilt_joint',
        reverse_pan_enabled=False,
        reverse_tilt_enabled=False,
        speed_ratio=0.5,
        status_update_rate_hz=5,
    )

    # ---- factoryLimits: PTXActuatorIF REQUIRES all 8 of these keys.
    LIMITS_DICT = dict(
        max_pan_hardstop_deg=175, min_pan_hardstop_deg=-175,
        max_tilt_hardstop_deg=90, min_tilt_hardstop_deg=-90,
        max_pan_softstop_deg=165, min_pan_softstop_deg=-165,
        max_tilt_softstop_deg=80, min_tilt_softstop_deg=-80,
    )

    device_info_dict = dict(device_name="", path="", serial_number="",
                            hw_version="", sw_version="")

    MAX_POSITION_UPDATE_RATE = 5

    serial_port = None
    serial_busy = False
    connected = False
    serial_num = ""
    hw_version = ""
    sw_version = ""

    speed_ratio = 0.5
    status_rate_hz = 5
    home_pan_deg = 0.0
    home_tilt_deg = 0.0
    current_position = [0.0, 0.0]       # [pan_deg, tilt_deg]
    position_times = [0.0, 0.0]
    soft_limits = [-165.0, 165.0, -80.0, 80.0]

    ptx_if = None
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
            self.port_str = self.drv_dict['DEVICE_DICT']['device_path']
            self.baud_int = int(self.drv_dict['DEVICE_DICT']['baud_str'])
            self.addr_str = self.drv_dict['DEVICE_DICT']['addr_str']
        except Exception as e:
            self.msg_if.pub_warn("Failed to load Device Dict " + str(e))
            nepi_sdk.signal_shutdown(self.node_name + ": no valid Device Dict")
            return

        self.connected = self.connect()
        if not self.connected:
            nepi_sdk.signal_shutdown(self.node_name + ": failed to connect")
            return
        self.msg_if.pub_info("Connected")

        self.cap_settings = self.getCapSettings()
        self.factory_settings = self.getFactorySettings()
        self.device_info_dict["device_name"] = self.device_name
        self.device_info_dict["path"] = self.device_path
        self.device_info_dict["serial_number"] = self.serial_num
        self.device_info_dict["hw_version"] = self.hw_version
        self.device_info_dict["sw_version"] = self.sw_version

        # ---- Register the pan-tilt with NEPI.
        self.ptx_if = PTXActuatorIF(
            device_info=self.device_info_dict,
            capSettings=self.cap_settings,
            factorySettings=self.factory_settings,
            settingUpdateFunction=self.settingUpdateFunction,
            getSettingsFunction=self.getSettings,
            factoryControls=self.FACTORY_CONTROLS,
            factoryLimits=self.LIMITS_DICT,
            # --- jog / relative motion
            stopMovingCb=self.stopMoving,
            movePanCb=self.movePan,             # (direction, duration)
            moveTiltCb=self.moveTilt,           # (direction, duration)
            movePanSpeedRatioCb=None,           # TODO: add if speed-during-jog supported
            moveTiltSpeedRatioCb=None,
            # --- soft limits
            getSoftLimitsCb=self.getSoftLimits,
            setSoftLimitsCb=self.setSoftLimits,
            # --- speed control
            getSpeedMaxCb=None,
            setSpeedMaxCb=None,
            getSpeedRatioCb=self.getSpeedRatio,
            setSpeedRatioCb=self.setSpeedRatio,
            getPanSpeedRatioCb=None,
            setPanSpeedRatioCb=None,
            getTiltSpeedRatioCb=None,
            setTiltSpeedRatioCb=None,
            # --- absolute positioning + feedback
            getPositionCb=self.getPosition,             # -> [pan_deg, tilt_deg]
            getPositionTimesCb=self.getPositionTimes,   # -> [pan_time, tilt_time]
            gotoPositionCb=self.gotoPosition,           # (pan_deg, tilt_deg)
            gotoPanPositionCb=self.gotoPanPosition,
            gotoTiltPositionCb=self.gotoTiltPosition,
            # --- homing
            goHomeCb=self.goHome,
            setHomePositionCb=self.setHomePosition,
            setHomePositionHereCb=self.setHomePositionHere,
            # --- orientation reporting (optional)
            getNavPoseCb=self.getNavPoseDict,
            navpose_update_rate=self.MAX_POSITION_UPDATE_RATE,
            deviceResetCb=self.resetDevice,
            calibrateCenterCB=None,
        )

        # Poll position at MAX_POSITION_UPDATE_RATE via a self-rescheduling timer.
        nepi_sdk.start_timer_process(1.0 / self.MAX_POSITION_UPDATE_RATE,
                                     self.updatePositionHandler, oneshot=True)
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

    def getStatusRate(self):
        return self.status_rate_hz

    def setStatusRate(self, val):
        self.status_rate_hz = int(val)
        return True

    #########################################################################
    # PTX CAPABILITY CALLBACKS  (TODO: implement your protocol in each)
    #########################################################################
    def stopMoving(self):
        self.send_msg('#' + self.addr_str + 'STOP')

    def movePan(self, direction, duration):
        # direction: +1 / -1 ; duration: seconds (0 => continuous until stop)
        self.send_msg('#' + self.addr_str + 'PAN' + ('+' if direction >= 0 else '-'))

    def moveTilt(self, direction, duration):
        self.send_msg('#' + self.addr_str + 'TLT' + ('+' if direction >= 0 else '-'))

    def getSoftLimits(self):
        return self.soft_limits              # [min_pan, max_pan, min_tilt, max_tilt]

    def setSoftLimits(self, min_pan, max_pan, min_tilt, max_tilt):
        self.soft_limits = [min_pan, max_pan, min_tilt, max_tilt]

    def getSpeedRatio(self):
        return self.speed_ratio

    def setSpeedRatio(self, ratio):
        self.speed_ratio = max(0.0, min(1.0, float(ratio)))

    def getPosition(self):
        return self.current_position         # [pan_deg, tilt_deg]

    def getPositionTimes(self):
        return self.position_times

    def gotoPosition(self, pan_deg, tilt_deg):
        self.send_msg('#' + self.addr_str + 'GOTO,%.2f,%.2f' % (pan_deg, tilt_deg))

    def gotoPanPosition(self, pan_deg):
        self.send_msg('#' + self.addr_str + 'GOTOP,%.2f' % pan_deg)

    def gotoTiltPosition(self, tilt_deg):
        self.send_msg('#' + self.addr_str + 'GOTOT,%.2f' % tilt_deg)

    def goHome(self):
        self.gotoPosition(self.home_pan_deg, self.home_tilt_deg)

    def setHomePosition(self, pan_deg, tilt_deg):
        self.home_pan_deg = pan_deg
        self.home_tilt_deg = tilt_deg

    def setHomePositionHere(self):
        self.home_pan_deg, self.home_tilt_deg = self.getPosition()

    def resetDevice(self):
        self.send_msg('#' + self.addr_str + 'RESET')

    def getNavPoseDict(self):
        # PTX navpose reports ORIENTATION only (degrees, ENU). Fill from feedback.
        navpose = copy.deepcopy(nepi_nav.BLANK_NAVPOSE_DICT)
        navpose['time_orientation'] = nepi_utils.get_time()
        navpose['has_orientation'] = True
        navpose['roll_deg'] = 0.0
        navpose['pitch_deg'] = self.current_position[1]   # tilt
        navpose['yaw_deg'] = self.current_position[0]      # pan
        return navpose

    #########################################################################
    # RAW SERIAL I/O + position poll
    #########################################################################
    def connect(self):
        try:
            self.serial_port = serial.Serial(self.port_str, self.baud_int, timeout=1)
        except Exception as e:
            self.msg_if.pub_warn("Serial open failed: " + str(e))
            return False
        response = self.send_msg('#' + self.addr_str + 'INFO')
        if response is None:
            return False
        # TODO: parse identity fields from your INFO reply.
        return True

    def send_msg(self, ser_msg):
        if self.serial_port is None:
            return None
        while self.serial_busy:
            nepi_sdk.sleep(0.01, 2)
        self.serial_busy = True
        response = None
        try:
            self.serial_port.reset_input_buffer()
            self.serial_port.write(bytearray(ser_msg + '\r', 'utf-8'))
            time.sleep(0.01)
            response = self.serial_port.readline().decode(errors='ignore').strip()
        except Exception as e:
            self.msg_if.pub_warn("Serial comm error: " + str(e))
        finally:
            self.serial_busy = False
        return response

    def updatePositionHandler(self, timer):
        # TODO: query live pan/tilt angles and cache them for getPosition().
        response = self.send_msg('#' + self.addr_str + 'POS?')
        if response is not None:
            try:
                parts = response.replace('#' + self.addr_str, '').split(',')
                self.current_position = [float(parts[-2]), float(parts[-1])]
                t = nepi_utils.get_time()
                self.position_times = [t, t]
            except Exception:
                pass
        # reschedule
        nepi_sdk.start_timer_process(1.0 / self.MAX_POSITION_UPDATE_RATE,
                                     self.updatePositionHandler, oneshot=True)

    def cleanup_actions(self):
        try:
            if self.serial_port is not None:
                self.serial_port.close()
        except Exception:
            pass


if __name__ == '__main__':
    node = PtxTemplateNode()
