# NEPI Driver Structure — How Drivers Work & How to Write One

This folder holds a **complete, copy-paste driver template for each NEPI device
type**. Every template is a working skeleton in the real house style, with the
correct interface class wired up and `TODO:` markers where you plug in your
device. This document explains the architecture they all share so you know
*why* each file looks the way it does. For the hands-on workflow (copy a
template, rename it, deploy it), see **`GETTING_STARTED.md`**.

```
nepi_drivers/
├── DRIVER_STRUCTURE.md      ← you are here (architecture reference)
├── GETTING_STARTED.md       ← create + deploy workflow
├── deploy_nepi_drivers.sh   ← deploys template drivers to the target src tree (all types, or pass categories)
├── idx_template/            ← Imaging / camera      (LAUNCH discovery + separate driver file)
├── lsx_template/            ← Lighting              (CALL discovery, serial in-node)
├── ptx_template/            ← Pan-Tilt / actuator   (CALL discovery, serial in-node)
├── npx_template/            ← Navigation / NavPose  (CALL discovery, TCP in-node)
└── rbx_template/            ← Robot / vehicle       (CALL discovery + optional companion node)
```

> These templates were reverse-engineered from the shipped drivers in
> `nepi_engine_ws/src/nepi_drivers/` and the interface classes in
> `nepi_engine_ws/src/nepi_engine/nepi_api/`. Where the older
> `nepi_drivers/CLAUDE.md` describes a free `discoveryFunction(...)` and
> `nepi_sdk.launch_node()`, that is stale — the current code is **class-based**
> and launches via **`nepi_drvs.launchDriverNode()`**, which is what these
> templates use.

---

## 1. The big picture

A NEPI driver is **not** a monolith. It is a small set of files that plug into
two pieces of framework you do **not** write:

- **`drivers_mgr`** (in `nepi_managers`) — the manager. It scans the install
  folder, reads each driver's `params.yaml`, and drives discovery on a ~1–3 s
  poll. It launches/kills nodes and owns the shared `active_paths_list`.
- **A device interface class** (`IDXDeviceIF`, `NPXDeviceIF`, `PTXActuatorIF`,
  `LSXDeviceIF`, `RBXRobotIF`, in `nepi_api`) — the ROS surface. It creates
  **every** publisher, subscriber, and service and exposes the standard NEPI
  API for that device type. Your node hands it callbacks; it does the ROS.

Your driver only provides three things: **how to find the hardware**
(discovery), **how to talk to it** (node + optional driver), and **what it is**
(params manifest).

```
                         reads params.yaml, polls discovery
   ┌────────────┐  ───────────────────────────────────────────►  ┌──────────────────┐
   │ drivers_mgr│                                                  │ <cat>_discovery.py│
   └────────────┘  ◄─── returns active_paths_list ───────────────  └──────────────────┘
                                                                        │ launchDriverNode()
                                                                        │ + set ~drv_dict param
                                                                        ▼
                                             ┌───────────────────────────────────────┐
                                             │ <cat>_node.py                           │
                                             │   reads ~drv_dict                        │
                                             │   (optional) imports <cat>_driver.py     │
                                             │   builds settings                        │
                                             │   ┌───────────────────────────────────┐ │
                                             │   │  <Type>DeviceIF(callbacks...)      │ │  ← creates all ROS topics/services
                                             │   └───────────────────────────────────┘ │
                                             │   spin()                                 │
                                             └───────────────────────────────────────┘
```

---

## 2. The files in a driver

Every driver is a flat set of files named `{cat}_{device}_{role}` where `{cat}`
is the 3-letter type prefix (`idx`, `npx`, `ptx`, `lsx`, `rbx`).

| File | Required? | Role |
|---|---|---|
| `{cat}_{device}_params.yaml` | **yes** | Manifest: names the files/classes, declares user options |
| `{cat}_{device}_discovery.py` | **yes** | Finds hardware, launches a node per device |
| `{cat}_{device}_node.py` | **yes** | The ROS node; registers with the interface class |
| `{cat}_{device}_driver.py` | optional | Raw hardware I/O, factored out (IDX cameras use this; serial devices usually don't) |

**Rule of thumb for the driver file:** if hardware I/O is a couple of serial
writes (LSX/PTX), do it inline in the node. If it involves an SDK, streaming
threads, or frame buffers (IDX cameras), factor it into a `_driver.py` the node
imports via `nepi_drvs.importDriverClass()`.

---

## 3. Two discovery models — `CALL` vs `LAUNCH`

This is the single most important architectural fork, set by
`DISCOVERY_DICT.process` in `params.yaml`. `drivers_mgr` dispatches on it.

### `CALL` — used by LSX, PTX, NPX, RBX
`drivers_mgr` imports your discovery class, instantiates it **once with no
arguments**, and then **calls `discoveryFunction(...)` every poll cycle** inside
its own process.

```python
class MyDiscovery:
    def __init__(self):                      # no init_node(), no spin()!
        self.logger = nepi_sdk.logger(log_name=...)

    def discoveryFunction(self, available_paths_list, active_paths_list,
                          base_namespace, drv_dict, retry_enabled=True):
        ...
        return active_paths_list             # MUST return the updated list

    def killAllDevices(self, active_paths_list):   # called on teardown
        ...
```

Use `CALL` when enumeration is cheap (a quick serial probe, checking a config
value). It is the simplest model.

### `LAUNCH` — used by IDX
Camera enumeration can be slow or blocking, so discovery runs as **its own
node**. `drivers_mgr` writes the driver's `drv_dict` to
`<discovery_node>/drv_dict` and `launchDriverNode()`s the discovery script.
Your discovery then `init_node()`s, reads `~drv_dict`, schedules its own
self-rescheduling `detectAndManageDevices(self, timer)` timer, and `spin()`s.

```python
class MyDiscovery:
    def __init__(self):
        nepi_sdk.init_node(name=self.DEFAULT_NODE_NAME)   # yes, it's a node
        self.updateDiscoveryOptions()                     # reads ~drv_dict
        nepi_sdk.start_timer_process(1.0, self.detectAndManageDevices, oneshot=True)
        nepi_sdk.on_shutdown(self.cleanup_actions)
        nepi_sdk.spin()
```

`drivers_mgr` afterward only checks whether the discovery node is still alive.

> Both models end up launching device nodes the **same** way (Section 4). Only
> *how discovery itself runs* differs.

---

## 4. The launch handshake (how config reaches the node)

When discovery decides a device is present, it does exactly two things, in this
order:

1. **Write the config to the ROS param server** at `<base>/<node_name>/drv_dict`.
   This is the full `drv_dict` (the parsed `params.yaml` `driver:` block) with a
   `DEVICE_DICT` sub-dict added — the per-instance facts discovery just learned
   (device name, path, serial addr, baud, ip:port, model, …).

   ```python
   self.drv_dict['DEVICE_DICT'] = {'device_name': ..., 'device_path': ..., ...}
   dict_param_name = nepi_sdk.create_namespace(base_namespace, node_name + "/drv_dict")
   nepi_sdk.set_param(dict_param_name, self.drv_dict)
   ```

2. **Launch the node:**
   ```python
   nepi_drvs.launchDriverNode(file_name, node_name, device_path=path_str)
   #   -> shells: rosrun nepi_drivers <file_name> __name:=<node_name> [_device_path:=...]
   ```

The node then reads its config straight back:
```python
self.drv_dict = nepi_sdk.get_param('~drv_dict', dict())
self.device_name = self.drv_dict['DEVICE_DICT']['device_name']
```

`drivers_mgr` injects one more key before the node sees it: **`drv_dict['path']`**
= the install directory (used by IDX to locate its `_driver.py`).

### Retry & backoff (both models)
- `NODE_LOAD_TIME_SEC` (~10 s) + a `launch_time_dict[path]` timestamp stop rapid
  relaunch loops.
- `dont_retry_list` permanently blacklists a device that failed when
  `retry_enabled` is False.
- Discovery also *purges*: each cycle it checks its launched nodes
  (`sub_process.poll()` and "is the path still present?") and kills + forgets
  any that died or disconnected, so the next cycle can rediscover them.

---

## 5. The node → interface-class contract (per type)

The node's real job: connect to hardware, build settings, then construct the
type's interface class, passing a callback for every capability the hardware
has and `None` for the rest. The interface class advertises only what you wire
up. `device_info` is required by **all** of them and needs these exact keys:

```python
device_info = dict(device_name="", path="", serial_number="", hw_version="", sw_version="")
```

| Type | Interface class | The callbacks that define it |
|---|---|---|
| **IDX** | `IDXDeviceIF` | `getColorImage`/`stopColorImageAcquisition` (and `getDepthMap`, `getPointcloud` for 3D), `getFramerate`, `setMaxFramerate`, `data_products=[...]`. `getColorImg()` returns a **5-tuple** `(ret, msg, cv2_img, timestamp, encoding)`. |
| **NPX** | `NPXDeviceIF` | Just `getNavPoseCb` — return a `nepi_nav.BLANK_NAVPOSE_DICT` with the `has_*` flags set for whatever the sensor provides (location/heading/altitude/orientation/position/depth). The IF polls it at `max_navpose_update_rate`. |
| **PTX** | `PTXActuatorIF` | Jog (`movePanCb`/`moveTiltCb`/`stopMovingCb`), absolute (`gotoPositionCb`, `getPositionCb`→`[pan_deg,tilt_deg]`), soft limits, speed ratio, homing, optional `getNavPoseCb`. Requires `factoryControls` + a `factoryLimits` dict with all 8 `*_pan/tilt_hard/softstop_deg` keys. |
| **LSX** | `LSXDeviceIF` | `getStatusFunction`→`DeviceLSXStatus` msg, `turnOnOffFunction`, `setIntensityRatioFunction` (0.0–1.0); optional color/kelvin/strobe/blink. `reports_temp`/`reports_power` flags. |
| **RBX** | `RBXRobotIF` | Ordered lists `states`/`modes`/`setup_actions`/`go_actions` + `get/setStateInd`, `get/setModeInd`, `setSetupActionInd`, `setGoActionInd`, `checkStopFunction`, `getBatteryPercentFunction`, an `AxisControls` DOF mask; optional autonomous `goto*`/home/`getNavPoseCb`. The IF returns the **index** into each list. |

### Settings — the shared plumbing every node repeats
Runtime-tunable parameters (shown in the RUI) use one pattern across all types:

- `CAP_SETTINGS` — what *can* be set (name, type, options/range).
- `FACTORY_SETTINGS` — defaults.
- `getSettings()` / `settingUpdateFunction(setting)` — read/write, decoding via
  `nepi_settings.get_data_from_setting(setting)` → `[name, type, data]`.

The shipped drivers resolve per-setting getters/setters through module-level
`global` functions + `globals()[name]`; the templates use `getattr(self, name)`
on bound methods instead — equivalent and easier to read. Either is fine.

`FACTORY_CONTROLS` is separate: it's the initial device state/config the IF
should assume (frame ids, initial on/off, FOV, etc.), not user-facing settings.

---

## 6. The params.yaml manifest

Single top-level `driver:` mapping. `drivers_mgr` reads it to wire everything
up; the values must match the actual files/classes on disk.

```yaml
driver:
  pkg_name: LSX_TEMPLATE            # unique id; also the PKG_NAME in the .py files
  display_name: Template LED Light  # shown in the RUI
  description: ...
  type: LSX                         # IDX | NPX | PTX | LSX | RBX
  group_id: None                    # optional grouping (e.g. ONVIF)
  NODE_DICT:      { file_name: ..._node.py,      class_name: ...Node }
  DRIVER_DICT:    { file_name: None,             class_name: None }     # or a real driver file
  DISCOVERY_DICT:
    file_name: ..._discovery.py
    class_name: ...Discovery
    process: CALL                   # CALL | LAUNCH  (see Section 3)
    OPTIONS:                        # user controls; discovery reads ['value']
      baud_rate: { type: Discrete, options: [All, '9600', ...], default: All, value: All }
      start_addr: { type: Int, options: ['1','255'], default: '1', value: '1' }
```

At runtime the dict the node receives = this `driver:` block **plus** the
injected `path` and `DEVICE_DICT` keys. `OPTIONS` value tokens like
`NEPI_NAV_IP_NMEA` or `SERIAL_DEVICES` are placeholders the framework resolves
at load time.

---

## 7. Build & install

Drivers are **not** registered individually. `nepi_drivers/CMakeLists.txt`
installs each category directory wholesale:

```cmake
install(DIRECTORY lsx_drivers/ DESTINATION /opt/nepi/nepi_engine/lib/nepi_drivers
        FILES_MATCHING PATTERN "*.py")
install(DIRECTORY lsx_drivers/ DESTINATION /opt/nepi/nepi_engine/lib/nepi_drivers
        FILES_MATCHING PATTERN "*.yaml")
```

So **all `*.py` and `*.yaml` files land flat** in
`/opt/nepi/nepi_engine/lib/nepi_drivers/`, and `drivers_mgr` scans that flat
folder. Adding a new driver needs **no CMake edit** — just drop the file-set
into the right `<cat>_drivers/` source folder and rebuild.

> Note: in this templates repo each driver is kept in its own `*_template/`
> subfolder for tidiness. In the real `nepi_drivers` tree the files live **flat**
> inside `<cat>_drivers/` (e.g. `idx_drivers/`), not in per-driver subfolders.

> **Creating and deploying a driver from these templates** — the step-by-step
> workflow (copy a template into your own repo, rename, fill TODOs, run
> `deploy_nepi_drivers.sh`) lives in `GETTING_STARTED.md`.

---

## 8. Gotchas (learned from the shipped drivers)

- **`class_name` mismatches.** e.g. `ptx_sidus_ss109_serial_params.yaml` declares
  `SidusSS109SerialNode` but the class is actually `SidusSS109SerialPTXNode`.
  The yaml wins for launching, but a mismatch means the node never starts. Keep
  them in sync.
- **Don't mutate `BLANK_NAVPOSE_DICT` in place.** It's a module-level dict.
  `copy.deepcopy()` it first (the shipped PTX driver mutates the shared one —
  the templates fix this). There's also a real `time_oreantation` typo in the
  shipped PTX node; the correct key is `time_orientation`.
- **Serial paths are not stable across reboots** (`/dev/ttyUSB0` ↔ `ttyUSB1`).
  Discovery re-probes every port each cycle; never hard-code an index.
- **CALL discovery must not call `init_node()`/`spin()`** — it runs inside
  `drivers_mgr`. Only `LAUNCH` discovery is its own node.
- **Surface hardware failures with `pub_warn`, not `pub_debug`**, so they show
  without Debug Mode enabled.
- **No hardware-in-the-loop CI.** These drivers aren't covered by automated
  tests requiring physical hardware — verify on the bench.
```
