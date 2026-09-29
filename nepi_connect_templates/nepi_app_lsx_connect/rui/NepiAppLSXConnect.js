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

import NepiIFImageViewer from "./Nepi_IF_ImageViewer"

import NepiIFConnectLSX from "./Nepi_IF_ConnectLSX"

@inject("ros")
@observer

// LSXConnect Application page.
//
// This is a minimal "connect example": the app node runs a ConnectLSXDeviceIF
// which owns the <app>/lsx_connect connect namespace (ConnectIFStatus selector
// state plus the select_topic subscriber). The page is laid out like the
// NepiDeviceLSX device page - image viewer on the left, selection and device
// panels stacked on the right - with the device selector, data, and controls
// all rendered by the reusable Nepi_IF_ConnectLSX component instead of the
// store's device list. Nepi_IF_LSX-Controls also brings the Device Settings and
// Advanced Settings panels with it, so this page owns nothing but the image viewer.
// It subscribes to the same ConnectIFStatus only to resolve the selected
// device topic for that viewer.
class NepiAppLSXConnect extends Component {

  constructor(props) {
    super(props)

    this.state = {
      appName: "app_lsx_connect",
      connectName: "lsx_connect",

      // Connect namespace (<app>/lsx_connect) the status listener is pointed at
      namespace: null,
      connect_status_msg: null,
      connectStatusListener: null,

      // Selected device topic (<device>/lsx), sourced from ConnectIFStatus
      selected_topic: 'None',
    }

    this.getBaseNamespace = this.getBaseNamespace.bind(this)
    this.getAppNamespace = this.getAppNamespace.bind(this)
    this.getConnectNamespace = this.getConnectNamespace.bind(this)

    this.updateConnectStatusListener = this.updateConnectStatusListener.bind(this)
    this.connectStatusListener = this.connectStatusListener.bind(this)

    this.renderImageViewer = this.renderImageViewer.bind(this)
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

  // The connect namespace the Nepi_IF_ConnectLSX component subscribes to, i.e.
  // <app>/lsx_connect, matching CONNECT_NAME in connect_device_if_lsx.py.
  getConnectNamespace() {
    const appNamespace = this.getAppNamespace()
    if (appNamespace !== null) {
      return appNamespace + "/" + this.state.connectName
    }
    return null
  }

  componentDidMount() {
    this.updateConnectStatusListener()
  }

  // Lifecycle method called when the component updates.
  // Re-point the connect listener when the connect namespace resolves or changes.
  componentDidUpdate(prevProps, prevState, snapshot) {
    const namespace = this.getConnectNamespace()
    if (namespace !== this.state.namespace) {
      this.updateConnectStatusListener()
    }
  }

  // Lifecycle method called just before the component unmounts.
  // Used to tear down the connect status listener.
  componentWillUnmount() {
    if (this.state.connectStatusListener) {
      this.state.connectStatusListener.unsubscribe()
    }
    this.setState({ connectStatusListener: null })
  }

  // Function for configuring and subscribing to the connect namespace status
  // topic (<app>/lsx_connect/status), message type ConnectIFStatus.
  updateConnectStatusListener() {
    const namespace = this.getConnectNamespace()
    if (this.state.connectStatusListener != null) {
      this.state.connectStatusListener.unsubscribe()
      this.setState({ connectStatusListener: null, connect_status_msg: null })
    }
    if (namespace != null && namespace !== 'None') {
      var connectStatusListener = this.props.ros.setupStatusListener(
        namespace + '/status',
        "nepi_interfaces/ConnectIFStatus",
        this.connectStatusListener
      )
      this.setState({ connectStatusListener: connectStatusListener })
    }
    this.setState({ namespace: namespace })
  }

  // Callback for ConnectIFStatus messages. Tracks the connected device topic so
  // the image viewer re-points when the connection changes.
  connectStatusListener(message) {
    this.setState({ connect_status_msg: message })
    if (message.selected_topic !== this.state.selected_topic) {
      this.setState({ selected_topic: message.selected_topic })
    }
  }

  renderImageViewer() {
    return (
      <React.Fragment>

        <NepiIFImageViewer
          id="lsxImageViewer"
        />

      </React.Fragment>
    )
  }

  render() {
    const connectNamespace = this.getConnectNamespace()
    const namespace = (this.state.selected_topic !== null) ? this.state.selected_topic : 'None'
    const device_selected = (namespace !== 'None')

    return (

      <Columns>
        <Column>

          <div style={{ display: 'flex' }}>

            <div style={{ width: "75%" }}>

              {(device_selected === true) ?
                this.renderImageViewer()
                : null}

            </div>

            <div style={{ width: '2%' }}>
              {}
            </div>

            <div style={{ width: "23%" }}>

              <NepiIFConnectLSX
                namespace={connectNamespace}
                show_selector={true}
                show_data={true}
                show_controls={true}
                show_controls_option={false}
                make_section={true}
                title={"LSX Connect"}
              />

            </div>

          </div>

        </Column>
      </Columns>

    )
  }
}

export default NepiAppLSXConnect
