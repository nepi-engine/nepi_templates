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

import NepiIFConnectIDX from "./Nepi_IF_ConnectIDX"

@inject("ros")
@observer

// IDXConnect Application page.
//
// This is a minimal "connect example": the app node runs a ConnectIDXDeviceIF
// which owns the <app>/idx_connect connect namespace (ConnectIFStatus selector
// state plus the select_topic subscriber). All of the selector, data, and
// controls rendering is handled by the reusable Nepi_IF_ConnectIDX component,
// which subscribes to that connect namespace and to the selected device's
// DeviceIDXStatus. This page just resolves the connect namespace and renders it.
class NepiAppIDXConnect extends Component {

  constructor(props) {
    super(props)

    this.state = {
      appName: "app_idx_connect",
      connectName: "idx_connect",
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

  // The connect namespace the Nepi_IF_ConnectIDX component subscribes to, i.e.
  // <app>/idx_connect, matching CONNECT_NAME in connect_device_if_idx.py.
  getConnectNamespace() {
    const appNamespace = this.getAppNamespace()
    if (appNamespace !== null) {
      return appNamespace + "/" + this.state.connectName
    }
    return null
  }

  render() {
    const connectNamespace = this.getConnectNamespace()
    const make_section = (this.props.make_section !== undefined) ? this.props.make_section : true

    return (
      <Columns>
        <Column>

          <NepiIFConnectIDX
            namespace={connectNamespace}
            title={"IDX Connect"}
            show_selector={true}
            show_data={true}
            show_controls={true}
            make_section={make_section}
          />

        </Column>
      </Columns>
    )
  }
}

export default NepiAppIDXConnect
