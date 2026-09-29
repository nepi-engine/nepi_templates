/*
#
# Copyright (c) 2024 Numurus <https://www.numurus.com>.
#
# This file is part of nepi rui (nepi_apps) repo
# (see https://https://github.com/nepi-engine/nepi_apps)
#
# License: NEPI RUI repo source-code and NEPI Images that use this source-code
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
 */

import React, { Component } from "react"
import { observer, inject } from "mobx-react"

import { Columns, Column } from "./Columns"

import NepiIFConnectMotor from "./Nepi_IF_ConnectMotor"

@inject("ros")
@observer

// MotorConnect Application page.
//
// This is a minimal "connect example": the app node runs a ConnectMotorsDeviceIF
// which owns the <app>/motor_connect connect namespace (ConnectIFStatus selector
// state plus the select_topic subscriber). The page is laid out like the
// NepiAppIDXConnect page - a wide left column and the device panels stacked in a
// narrow right column - with the device selector, data, and controls all
// rendered by the reusable Nepi_IF_ConnectMotor component.
// Nepi_IF_Motor-Controls also brings the Device Settings and Advanced Settings
// panels with it, so this page owns nothing itself.
//
// There is no motor device page and no viewer for a motor device, so the left
// column has no content to host. It is kept only so this page matches the layout
// of its sibling connect examples; collapse it if a wider device panel reads
// better for a given deployment.
class NepiAppMotorConnect extends Component {

  constructor(props) {
    super(props)

    this.state = {
      appName: "app_motor_connect",
      connectName: "motor_connect",
    }

    this.getBaseNamespace = this.getBaseNamespace.bind(this)
    this.getAppNamespace = this.getAppNamespace.bind(this)
    this.getConnectNamespace = this.getConnectNamespace.bind(this)
  }

  getBaseNamespace() {
    const { namespacePrefix, deviceId } = this.props.ros
    if (namespacePrefix !== null && deviceId !== null) {
      return "/" + namespacePrefix + "/" + deviceId
    }
    return null
  }

  getAppNamespace() {
    const base = this.getBaseNamespace()
    if (base !== null) {
      return base + "/" + this.state.appName
    }
    return null
  }

  // The connect namespace the Nepi_IF_ConnectMotor component subscribes to, i.e.
  // <app>/motor_connect, matching CONNECT_NAME in connect_device_if_motor.py.
  getConnectNamespace() {
    const appNamespace = this.getAppNamespace()
    if (appNamespace !== null) {
      return appNamespace + "/" + this.state.connectName
    }
    return null
  }

  render() {
    const connectNamespace = this.getConnectNamespace()

    return (

      <Columns>
        <Column>

          <div style={{ display: 'flex' }}>

            <div style={{ width: "75%" }}>
              {}
            </div>

            <div style={{ width: '2%' }}>
              {}
            </div>

            <div style={{ width: "23%" }}>

              <NepiIFConnectMotor
                namespace={connectNamespace}
                show_selector={true}
                show_data={true}
                show_controls={true}
                show_controls_option={false}
                make_section={true}
                title={"Motor Connect"}
              />

            </div>

          </div>

        </Column>
      </Columns>

    )
  }
}

export default NepiAppMotorConnect
