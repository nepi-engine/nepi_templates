# NEPI Connect Examples

This folder holds minimal example apps that show how to consume another NEPI
node's API through a `Connect<X>IF` client interface. Each app is meant to be
copied and adapted as a starting point for your own integration.

## What a Connect IF is

A `Connect<X>IF` (for example `ConnectDataIF`, `ConnectIDXDeviceIF`,
`ConnectNodeIF`) is a client-side interface. It is the counterpart to the
`<X>IF` that a device, manager, or data node uses to publish its API. The
connect side lets a different node or app consume that API without knowing any
of the ROS plumbing.

Taking `ConnectDataIF` as the example, it lives inside an app node and:

1. Discovers available sources of a given type (for image data, topics
   reporting `ImageStatus`).
2. Exposes a stable connect namespace (`<app>/data_connect`) that publishes one
   `ConnectIFStatus` and accepts a `select_topic` command.
3. Connects to the selected source and hands the app simple getters (image
   topic, encoding, dimensions) so the app never touches the raw device topics.

## Why they are helpful

- **Decoupling.** The consumer talks to one predictable namespace, not to
  whatever device happens to be present. Sources can come and go; the app just
  sees `available_topics` update and picks one. No hard-coded topic names.

- **A uniform selector contract.** Every connect IF speaks the same
  `ConnectIFStatus` message (available/selected topics, connected flag, and the
  `show_*` visibility flags). That is why one small reusable RUI component per
  type (`Nepi_IF_ConnectData`, `Nepi_IF_ConnectIDX`, and so on) can drive the
  whole UI, and why the app page is just a thin mount.

- **The IF is the whole surface.** The app and its UI only ever use what the IF
  exposes. This is the "IF-only" rule. You can swap the underlying device,
  change the wiring, or restructure the producer node, and nothing downstream
  breaks as long as the IF contract holds.

- **Discovery and persistence for free.** The IF handles finding sources,
  connecting and reconnecting, and (via the config manager) remembering the
  selected source across restarts. The app author writes none of that.

- **They are teachable examples.** These apps show the minimum needed to consume
  each kind of NEPI resource: run the IF, mount the matching reusable RUI
  component, done.

## How the pieces line up (data example)

| Layer                    | Data example                                        |
| ------------------------ | --------------------------------------------------- |
| Producer publishes API   | image / IDX node with `ImageStatus`                 |
| Consumer IF (client)     | `ConnectDataIF` in the app node                     |
| Connect namespace        | `<app>/data_connect` (`ConnectIFStatus` + `select_topic`) |
| Reusable RUI component   | `Nepi_IF_ConnectData.js` (selector + image viewer)  |
| Thin app page            | `NepiAppDataConnect.js`                             |

In short: the connect IFs turn "find, select, connect to, and read another
node's API" into a standard, reusable, swappable building block, so both app
code and UI stay small and resilient.

## Examples in this folder

- `nepi_app_data_connect` - connect to a data (image) source and view it.
- `nepi_app_idx_connect` - connect to an IDX imaging device and show its
  telemetry and controls.
- `nepi_app_lsx_connect` - connect to an LSX light device.
- `nepi_app_npx_connect` - connect to an NPX device.
- `nepi_app_pan_tilt_connect` - connect to a pan/tilt (PTX) device.

## RUI structure of a connect example

Each example splits its RUI into two files:

1. A thin app page `NepiApp<X>Connect.js` in the app's own `rui/` folder. It
   resolves the connect namespace (`<base>/<app>/<connect_name>`) and mounts the
   reusable component.
2. A reusable `Nepi_IF_Connect<X>.js` committed in the nepi_rui source tree
   (`src/rui_webserver/rui-app/src/`), not in the app folder. It subscribes to
   the connect namespace `ConnectIFStatus`, renders the selector, and renders the
   data section (for data/image sources it mounts `Nepi_IF_ImageViewer` on the
   IF-reported selected topic).

Registration happens through the app's `params/<x>_connect_app_params.yaml`
`RUI_DICT` (declaring `rui_main_file` and `rui_main_class`). The RUI build
(`build_nepi_rui.sh`) copies the app page into the RUI source and injects the
import and class-map entries into `Nepi_IF_Apps.js`. The app appears in the
selector from the running node; if no matching bundled component exists, the
page renders blank, so a reusable `Nepi_IF_Connect<X>.js` plus a RUI rebuild are
both required for a new example.
