# NEPI App Structure — How Apps Work & How to Write One

This folder holds a **complete, copy-paste NEPI app template**
(`nepi_app_template/`) plus the deploy script. This document explains the
architecture an app plugs into so you know *why* each file looks the way it
does. For the hands-on workflow (copy, rename, deploy), see
**`GETTING_STARTED.md`**.

```
nepi_apps/
├── APP_STRUCTURE.md         ← you are here (architecture reference)
├── APP_PATTERNS.md          ← add-on patterns with real code excerpts
├── GETTING_STARTED.md       ← create + deploy workflow
├── deploy_nepi_apps.sh      ← deploys app package folders to the target src tree
└── nepi_app_template/       ← the template app (a complete catkin package)
    ├── scripts/template_app_node.py    ← the ROS node
    ├── params/template_app_params.yaml ← manifest read by apps_mgr
    ├── msg/NepiAppTemplateStatus.msg   ← the app's status message
    ├── api/connect_app_template.py     ← client class other nodes can import
    ├── rui/NepiAppTemplate.js          ← React page shown in the RUI
    ├── etc/  srv/                      ← placeholders (house convention)
    ├── CMakeLists.txt  package.xml     ← catkin package + install rules
    └── LICENSE
```

> Reverse-engineered from the shipped apps in `nepi_engine_ws/src/nepi_apps/`
> (`nepi_app_fake_gps` is the cleanest reference), `apps_mgr.py` in
> `nepi_managers`, and `build_nepi_rui.sh`.

---

## 1. The big picture

A NEPI app is a self-contained capability (simulation, viewing, automation...)
packaged as its own catkin package. Two pieces of framework you do **not**
write manage it:

- **`apps_mgr`** (in `nepi_managers`) — scans for installed apps every 5 s,
  reads each app's params yaml, and launches/kills the app node based on its
  enabled ("active") state. Users enable/disable apps from the RUI.
- **`NodeClassIF`** (in `nepi_api.node_if`) — the node-side framework class.
  Your node describes its params, publishers, and subscribers as four plain
  dicts; `NodeClassIF` creates all the ROS plumbing, persists params, and
  auto-creates the standard `save_config`/`reset_config`/`factory_reset_config`
  topics.

Unlike drivers (which register hardware-type interface classes with fixed
callback contracts), **every app uses the same skeleton**. Apps differ only in
what they compose inside it — a worker thread, extra data publishers,
subscriptions to other nodes.

```
  ┌──────────┐  scans share/nepi_apps/params/*.yaml every 5 s
  │ apps_mgr │ ────────────────────────────────────────────►  APP_DICT / RUI_DICT
  └──────────┘
       │  for each ACTIVE app:
       │    1. set <base>/<node_name>/app_dict param
       │    2. load saved config yaml (if any) into the node's namespace
       │    3. nepi_sdk.launch_node(pkg_name, app_file, node_name)   →  rosrun
       ▼
  ┌──────────────────────────────────────────────┐
  │ <name>_app_node.py                            │
  │   NodeClassIF(configs, params, pubs, subs)    │ ← creates all ROS interfaces
  │   1 Hz latched status publisher               │
  │   spin()                                      │
  └──────────────────────────────────────────────┘
```

---

## 2. Discovery & launch (apps_mgr)

- `apps_mgr` scans the installed params folder
  (`/opt/nepi/nepi_engine/share/nepi_apps`) for yaml files whose name contains
  `params`.
- From each yaml it requires the top-level **`APP_DICT`** block; **`RUI_DICT`**
  is optional. Inside `APP_DICT`, `pkg_name` (the dict key) and `app_file` are
  hard requirements — if the node file doesn't exist at
  `/opt/nepi/nepi_engine/lib/<pkg_name>/<app_file>`, the app is purged from the
  list. `group_name`, `node_name`, `config_file`, `description` are used later
  and should always be set.
- Launch is a plain **`rosrun`** via `nepi_sdk.launch_node(pkg_name, app_file,
  node_name)` — there are no `.launch` files. Before launching, apps_mgr writes
  the app's dict to the `<node_namespace>/app_dict` param and loads the app's
  saved config yaml if one exists.
- `active` (user-enabled) is persisted by apps_mgr; `running` is a live
  `check_node_by_name` check. A node that dies on its own gets marked inactive.

---

## 3. The node skeleton

Every app node follows this exact shape (see the template or
`fake_gps_app_node.py`):

```python
nepi_sdk.init_node(name=self.DEFAULT_NODE_NAME)
self.msg_if = MsgIF(log_name=self.class_name)

self.CFGS_DICT   = {'init_callback': self.initCb, 'reset_callback': self.resetCb,
                    'factory_reset_callback': self.factoryResetCb,
                    'init_configs': True, 'namespace': self.node_namespace}
self.PARAMS_DICT = {'enabled': {'namespace': self.node_namespace, 'factory_val': False}, ...}
self.PUBS_DICT   = {'status_pub': {'namespace': ..., 'topic': 'status',
                    'msg': <YourStatusMsg>, 'qsize': 1, 'latch': True}, ...}
self.SUBS_DICT   = {'set_enabled': {'namespace': ..., 'topic': 'set_enabled', 'msg': Bool,
                    'qsize': 10, 'callback': self.setEnabledCb, 'callback_args': ()}, ...}

self.node_if = NodeClassIF(configs_dict=self.CFGS_DICT, params_dict=self.PARAMS_DICT,
                           pubs_dict=self.PUBS_DICT, subs_dict=self.SUBS_DICT)
self.node_if.wait_for_ready()
self.initCb(do_updates=True)
nepi_sdk.start_timer_process(1.0, self.statusPublishCb)     # 1 Hz latched status
nepi_sdk.on_shutdown(self.cleanup_actions)
nepi_sdk.spin()
```

Conventions the framework relies on:
- **Status**: one latched `status` topic publishing your app's Status msg at
  ~1 Hz *and* immediately after any state change. The RUI page subscribes to it.
- **Params**: read with `self.node_if.get_param(name)`, write with
  `set_param(name, val)` + `save_config()` in each setter callback. The
  `initCb/resetCb/factoryResetCb` trio restores state from the param layer.
- **Publish anything the UI needs to render** (e.g. the template publishes its
  `options` list in status so the RUI menu always matches the node).

### Optional add-ons (compose inside the skeleton)

> Each row is expanded with real, copy-paste code excerpts in
> **`APP_PATTERNS.md`**.

| Your app needs… | Pattern | Crib from |
|---|---|---|
| A background worker | daemon `threading.Thread` + `threading.Lock` around shared state | `nepi_app_fake_gps` (`_simThreadLoop`) |
| To publish navpose data | `NavPoseIF` from `nepi_api.data_if` | `nepi_app_fake_gps` (`_setupNavpose`) |
| Periodic resource discovery | self-rescheduling oneshot timer scanning `nepi_sdk.find_topics_by_msg(...)` | `nepi_app_image_viewer` (`updaterCb`) |
| Save-data (snapshots, logging) | `Nepi_IF_SaveData` in the RUI + `ConnectSaveDataIF` in the connector | `nepi_app_image_viewer` |
| To drive devices / consume AI topics | `Connect*` classes from `nepi_api` | `nepi_app_pan_tilt_auto` |
| To publish images / video from files | data publishers from `nepi_api.data_if` | `nepi_app_file_pub_img` / `_vid` |

---

## 4. The params.yaml manifest

```yaml
APP_DICT:
  display_name: Template App          # shown in the RUI
  description: ...
  pkg_name: nepi_app_template         # MUST equal the catkin package name
  group_name: DATA                    # RUI menu bucket: DEVICE | DATA | PROCESS | AUTOMATION | SYSTEM
  config_file: app_template.yaml      # saved-config filename apps_mgr loads at launch
  app_file: template_app_node.py      # the node script (existence checked!)
  node_name: app_template             # ROS node name apps_mgr launches under
  license_type: 3-clause BSD
  license_link: https://opensource.org/licenses/BSD-3-Clause
RUI_DICT:                             # optional -- omit for headless apps
  rui_files:                          # every .js file this app installs
  - NepiAppTemplate.js
  rui_main_file: NepiAppTemplate.js
  rui_main_class: NepiAppTemplate     # MUST equal the exported React class name
```

`group_name` must be one of the RUI selector buckets or the app won't appear
in any menu. `rui_main_class` must exactly match the class the js file
`export default`s (it may differ from the filename — image_viewer exports
`ImageViewerApp` from `NepiAppImageViewer.js` — but yaml and export must agree).

---

## 5. The connect API (`api/connect_app_*.py`)

A thin client class other nodes can import to command your app without knowing
its topic layout. It mirrors your node's interface through
`ConnectNodeClassIF`: your node's *subscribers* become the connector's
*publishers*, and your status topic becomes a subscription cached into
`status_msg`. It installs into the shared `nepi_api` package, so consumers
write `from nepi_api.connect_app_template import ConnectAppTemplate`.

**Gotcha:** every pub/sub entry in the connector must use the **target app's**
namespace (`self.namespace`, resolved from the constructor arg or
`<base>/<app_node_name>`), never the calling node's `self.node_namespace`.
Getting this wrong publishes into the caller's own namespace and silently does
nothing.

---

## 6. RUI integration

How your React page ends up in the web UI:

1. **Install**: CMake copies `rui/*.js` flat into
   `/opt/nepi/nepi_rui/src/rui_webserver/rui-app/src/` and your params yaml
   into `.../rui-app/src/apps/`.
2. **Injection**: `build_nepi_rui.sh` walks `src/apps/*.yaml`, reads
   `rui_main_file` + `rui_main_class`, and sed-injects an `import` line and a
   `["<class>", <class>]` entry into the `appsClassMap` in `Nepi_IF_Apps.js`.
3. **Runtime**: the RUI subscribes to `apps_mgr/status`; the app selector lists
   apps by `group_name` **only while they are running**, and mounts your
   component via `appsClassMap.get(rui_main_class)`.

So RUI changes require **rebuilding the RUI** (`build_nepi_rui.sh` → npm
build), not just restarting the node.

House rules for the page itself (see the template):
- Subscribe with `setupStatusListener(ns + '/status', '<pkg>/<StatusMsg>', cb)`
  and unsubscribe in `componentWillUnmount`.
- Send commands with the Store helpers (`sendBoolMsg`, `sendStringMsg`,
  `sendFloatMsg`, `sendTriggerMsg` for Empty). Check Store.js before assuming a
  helper exists.
- Editable `Input` boxes: buffer edits in state, mark the element modified
  (`setElementStyleModified`) while dirty, and commit on Enter with
  `clearElementStyleModified` — never send on every keystroke.

---

## 7. Build & install

Each app is its own catkin package; `CMakeLists.txt` installs to fixed NEPI
locations:

| Source | Installed to |
|---|---|
| `scripts/*_node.py` | `lib/<pkg_name>/` (catkin bin, executable) |
| `params/` | `${NEPI_ENGINE}/share/nepi_apps/params` **and** `${NEPI_RUI}/.../src/apps` |
| `api/*.py` | `${NEPI_ENGINE}/lib/python3/dist-packages/nepi_api/` |
| `rui/` | `${NEPI_RUI}/src/rui_webserver/rui-app/src/` |
| `msg/*.msg` | built by `generate_messages` into the `<pkg_name>.msg` Python module |
| `etc/` | catkin global etc |

Adding an app = dropping the package folder into
`nepi_engine_ws/src/nepi_apps/` and rebuilding. No registry edits.

---

## 8. Gotchas (learned from the shipped apps)

- **`pkg_name` is load-bearing three ways**: it's the catkin package name, the
  rosrun package for launch, and the Python module for your msg import
  (`from <pkg_name>.msg import ...`). Rename all together.
- **`rui_main_class` vs export mismatch** silently gives a blank page — the
  classMap lookup returns undefined.
- **The RUI label above an app page is blank by design-accident**: the RUI
  reads `rui_menu_name`, but nothing ever populates it (not in `AppStatus.msg`,
  not in the yaml). Don't be surprised by the missing label.
- **Apps only appear in the selector while running** — an enabled-but-crashed
  app vanishes from the menu instead of showing an error.
- **Connector namespace bug** (Section 5) — the most common copy-paste mistake.
- **`ConnectNodeClassIF` takes no `namespace`/`log_class_name` kwargs.** Several
  shipped `connect_app_*` files pass them anyway — they'd `TypeError` if ever
  instantiated (they're currently unused in-tree, which is how the bug
  survives). The target namespace rides in the per-entry `namespace` fields of
  the pubs/subs dicts. The template's connector shows the correct call.
- **No `srv/` support is wired** in the shipped apps (placeholder folders
  only); services go through `NodeClassIF` services_dict if needed.
- **`apps_mgr` package install/remove functions are currently broken** in
  `nepi_apps.py` (corrupted commented-out region) — deploy apps via the source
  tree + rebuild, not via .zip package install.
