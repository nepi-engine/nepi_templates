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

import Section from "./Section"
import { Columns, Column } from "./Columns"
import Label from "./Label"
import Select, { Option } from "./Select"

import NepiIFImageViewer from "./Nepi_IF_ImageViewer"

import NepiIFConnectIDX from "./Nepi_IF_ConnectIDX"

@inject("ros")
@observer

// IDXConnect Application page.
//
// This is a minimal "connect example": the app node runs a ConnectIDXDeviceIF
// which owns the <app>/idx_connect connect namespace (ConnectIFStatus selector
// state plus the select_topic subscriber). The page is laid out like the
// NepiDeviceIDX device page - image viewer on the left, selection and device
// panels stacked on the right - with the device selector, data, and controls
// all rendered by the reusable Nepi_IF_ConnectIDX component instead of the
// store's device list. Nepi_IF_IDX-Controls also brings the Device Settings and
// Advanced Settings panels with it, so this page owns nothing but the image
// viewer and its data product selector. It subscribes to the same
// ConnectIFStatus only to resolve the selected device topic for those two.
class NepiAppIDXConnect extends Component {

  constructor(props) {
    super(props)

    this.state = {
      appName: "app_idx_connect",
      connectName: "idx_connect",

      // Connect namespace (<app>/idx_connect) the status listener is pointed at
      namespace: null,
      connect_status_msg: null,
      connectStatusListener: null,

      // Selected device topic (<device>/idx), sourced from ConnectIFStatus
      selected_topic: 'None',

      // Image viewer data product selection, local to this page
      data_topic: 'None',
      data_product: 'None',
    }

    this.getBaseNamespace = this.getBaseNamespace.bind(this)
    this.getAppNamespace = this.getAppNamespace.bind(this)
    this.getConnectNamespace = this.getConnectNamespace.bind(this)

    this.updateConnectStatusListener = this.updateConnectStatusListener.bind(this)
    this.connectStatusListener = this.connectStatusListener.bind(this)

    this.createDataProductOptions = this.createDataProductOptions.bind(this)
    this.onDataProductSelected = this.onDataProductSelected.bind(this)
    this.renderDataProductSelector = this.renderDataProductSelector.bind(this)

    this.renderSelection = this.renderSelection.bind(this)
    this.findImageTopic = this.findImageTopic.bind(this)
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

  // The connect namespace the Nepi_IF_ConnectIDX component subscribes to, i.e.
  // <app>/idx_connect, matching CONNECT_NAME in connect_device_if_idx.py.
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
  // topic (<app>/idx_connect/status), message type ConnectIFStatus.
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

  // Callback for ConnectIFStatus messages. Clears the data product selection
  // whenever the connected device changes so the image viewer re-resolves.
  connectStatusListener(message) {
    this.setState({ connect_status_msg: message })
    if (message.selected_topic !== this.state.selected_topic) {
      this.setState({
        selected_topic: message.selected_topic,
        data_topic: 'None',
        data_product: 'None'
      })
    }
  }

  // Function for creating data product options for Select input
  createDataProductOptions() {
    const namespace = (this.state.selected_topic !== null) ? this.state.selected_topic : 'None'
    const capabilities = this.props.ros.idxDevices[namespace]
    const data_products = capabilities ? capabilities.data_products : []

    var items = []
    var data_product
    var data_topic

    for (var i = 0; i < data_products.length; i++) {
      data_product = data_products[i]
      data_topic = namespace + '/' + data_product
      items.push(<Option value={data_topic}>{data_product}</Option>)
    }

    const sel_data_topic = this.state.data_topic
    if (items.length === 0) {
      items.push(<Option value={"None"}>{"None"}</Option>)
      if (sel_data_topic !== 'None') {
        this.setState({
          data_topic: "None",
          data_product: "None",
        })
      }
    }
    else if (sel_data_topic === 'None' || sel_data_topic == null) {
      this.setState({
        data_topic: namespace + '/' + data_products[0],
        data_product: data_products[0],
      })
    }

    return items
  }

  // Handler for data product selection
  onDataProductSelected(event) {
    const index = event.nativeEvent.target.selectedIndex
    const text = event.nativeEvent.target[index].text
    const value = event.target.value

    this.setState({
      data_topic: value,
      data_product: text,
    })
  }

  renderDataProductSelector() {
    const data_topic = this.state.data_topic

    return (

      <React.Fragment>

        <div align={"left"} textAlign={"left"}>
          <Label title={"Data Product"}>
            <Select
              id="topicSelect"
              onChange={this.onDataProductSelected}
              value={data_topic}
            >
              {this.createDataProductOptions()}
            </Select>
          </Label>
        </div>

      </React.Fragment>
    )
  }

  // Data product selection section. Local to this page and drives the image
  // viewer; the device selection itself belongs to the connect component.
  renderSelection() {
    const device_selected = (this.state.selected_topic !== null && this.state.selected_topic !== 'None')

    if (device_selected === false) {
      return (
        <Columns>
          <Column>

          </Column>
        </Columns>
      )
    }

    return (
      <Section title={"Selection"}>

        {this.renderDataProductSelector()}

      </Section>
    )
  }

  findImageTopic(data_product) {
    const namespace = (this.state.selected_topic !== null) ? this.state.selected_topic : 'None'
    const dp_namespace = namespace + '/' + data_product
    var image_topic = 'None'
    const { imageTopics } = this.props.ros
    var image_name = ''
    for (var i = 0; i < imageTopics.length; i++) {
      image_name = imageTopics[i].split('/').pop()
      if ((imageTopics[i].indexOf(dp_namespace) !== -1) && (image_name !== 'depth_map')) {
        image_topic = imageTopics[i]
        break
      }
    }
    return image_topic
  }

  renderImageViewer() {
    const image_topic = this.findImageTopic(this.state.data_product)
    const image_text = image_topic.split('/idx')[0].split('/').pop() + '-' + this.state.data_product

    return (
      <React.Fragment>
        <Columns>
          <Column equalWidth={false}>

            <NepiIFImageViewer
              image_topic={image_topic}
              title={image_text}
              data_product={this.state.data_product}
              hideQualitySelector={false}
              show_topic_selector={false}
              show_all_config_options={false}
            />

          </Column>
        </Columns>
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

              {this.renderSelection()}

              {(device_selected === true) ?
                this.renderImageViewer()
                : null}

            </div>

            <div style={{ width: '2%' }}>
              {}
            </div>

            <div style={{ width: "23%" }}>



              <NepiIFConnectIDX
                namespace={connectNamespace}
                show_selector={true}
                show_data={true}
                show_controls={true}
                show_controls_option={false}
                make_section={true}
                title={"IDX Connect"}
              />

            </div>

          </div>

        </Column>
      </Columns>

    )
  }
}

export default NepiAppIDXConnect
