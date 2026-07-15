# Getting Started — Creating & Deploying a NEPI App from the Template

This is the practical workflow for turning `nepi_app_template/` into a real
app and getting it onto a NEPI device. For *how apps work* (apps_mgr, the
NodeClassIF skeleton, RUI injection), read `APP_ARCHITECTURE.md`.

---

## 1. Create your app from the template

1. **Copy the `nepi_app_template/` folder** into your own repo/location,
   **along with `deploy_nepi_apps.sh`** sitting next to it. `setup_new_app.sh`
   rides along inside the folder.
2. **Rename everything with `setup_new_app.sh`** (recommended). Edit the
   EDIT-THESE block at the top of `nepi_app_template/setup_new_app.sh`
   (`APP_SUFFIX`, `DISPLAY_NAME`, `DESCRIPTION`, `GROUP_NAME`, and optional
   `SHORT_NAME`), then run it:

   ```bash
   cd nepi_app_template
   ./setup_new_app.sh --dry-run   # preview the full rename plan
   ./setup_new_app.sh             # do it (renames the folder + every file/token)
   ```

   `APP_SUFFIX` (snake_case, e.g. `nav_sim`) drives every derived name so they
   stay consistent: package `nepi_app_nav_sim`, node `app_nav_sim`, node class
   `NepiNavSimApp`, connector `ConnectAppNavSim`, msg `NepiAppNavSimStatus`, RUI
   class `NepiAppNavSim`, plus the `scripts/`, `params/`, `msg/`, `rui/`, `api/`
   filenames. Set `SHORT_NAME` (e.g. `PTAuto`) when the full name is too long
   for the RUI class; the msg type and package name stay full so the node and
   RUI still agree. Delete the script from your app once you have run it.

   <details><summary>Or rename by hand — the full token checklist</summary>

   The rename must stay consistent everywhere: `pkg_name` is used as the catkin
   package name, the rosrun package, AND the msg import module.

   | File | What to rename |
   |---|---|
   | folder | `nepi_app_template` → `nepi_app_<name>` |
   | `package.xml` | `<name>nepi_app_template</name>` |
   | `CMakeLists.txt` | `project(nepi_app_template)`, the msg filename, the script path |
   | `params/*.yaml` | filename (must keep `params` in it!), `APP_DICT` fields (`pkg_name`, `app_file`, `node_name`, `config_file`, `display_name`, `description`, `group_name`), `RUI_DICT` fields |
   | `msg/NepiAppTemplateStatus.msg` | filename + fields you need |
   | `scripts/template_app_node.py` | filename, `from nepi_app_template.msg import ...`, class name, `DEFAULT_NODE_NAME` |
   | `api/connect_app_template.py` | filename, msg import, class name, `APP_NODE_NAME` |
   | `rui/NepiAppTemplate.js` | filename, class name + `export default`, `state.appName`, the status msg type string `"nepi_app_template/NepiAppTemplateStatus"` |

   Three fields must agree or the app silently fails:
   - `APP_DICT.pkg_name` == catkin package name (package.xml / CMake project)
   - `APP_DICT.app_file` == the node script filename
   - `RUI_DICT.rui_main_class` == the React class your js `export default`s

   </details>

3. **Pick the right `group_name`** (`DEVICE`, `DATA`, `PROCESS`, `AUTOMATION`,
   or `SYSTEM`) — it decides which RUI selector menu the app appears in.

4. **Fill in your logic:**
   - *node* — replace the example `enabled/option/value` state with your real
     params, pubs, subs, and put your work in `updaterCb` / a worker thread.
     Keep the 1 Hz latched status pattern.
   - *msg* — put everything the RUI needs to render into the Status msg.
   - *rui* — mirror the status fields into state; send commands with the Store
     helpers (`sendBoolMsg`/`sendStringMsg`/`sendFloatMsg`/`sendTriggerMsg`).
     For editable Input boxes keep the Enter-to-commit + modified-style
     pattern already in the template.
   - *api* — keep the connector's pubs mirroring your node's subs. All
     entries must use the app's namespace (`self.namespace`), never
     `self.node_namespace`.
   - For worker threads, NavPose publishing, resource discovery, SaveData,
     device control, and image publishing, see **`APP_PATTERNS.md`** — each
     pattern comes with real code excerpts from the shipped app that does it
     best.

5. **Syntax-check:**
   ```bash
   python3 -m py_compile scripts/*_node.py api/connect_app_*.py
   python3 -c "import yaml; d=yaml.safe_load(open('params/<name>_app_params.yaml')); assert 'APP_DICT' in d"
   ```

---

## 2. Deploy to the NEPI src tree

`deploy_nepi_apps.sh` syncs each app package folder (as a folder, not
flattened) into the target's source tree at:

```
${NEPI_TARGET_SRC_DIR}/nepi_engine_ws/src/nepi_apps/<app_folder>/
```

Usage:

```bash
export NEPI_REMOTE_SETUP=0             # 0 = running on the target, 1 = from a dev host
./deploy_nepi_apps.sh                  # deploy every nepi_app_* folder next to the script
./deploy_nepi_apps.sh nepi_app_mything # or just one
```

Remote mode (`NEPI_REMOTE_SETUP=1`) additionally needs `NEPI_TARGET_IP` (taken
from `NEPI_IP`) and the default SSH key at
`~/ssh_keys/nepi_engine_default_private_ssh_key`.

---

## 3. Build & watch it come up

1. **Rebuild the workspace** so the package installs (node → `lib/<pkg>`,
   params → `share/nepi_apps/params`, api → `nepi_api`, rui → the RUI src).
2. **Rebuild the RUI** (`build_nepi_rui.sh`) — this is the step that injects
   your `rui_main_class` into the RUI's `appsClassMap`. Skipping it means the
   app page renders blank.
3. Restart NEPI. In the RUI **Apps manager**, your app should be listed —
   enable it. `apps_mgr` then launches the node (`rosrun <pkg> <app_file>`);
   watch its log for your node's "Initialization Complete".
4. The app page appears in its `group_name` menu **only while the node is
   running**.

---

## Reference apps to crib from

| Your app is like… | Read the shipped app |
|---|---|
| Data generator / injector with a worker thread | `nepi_apps/nepi_app_fake_gps` |
| Viewer / topic selector (RUI-heavy, thin node) | `nepi_apps/nepi_app_image_viewer` |
| File-based data publisher | `nepi_apps/nepi_app_file_pub_img`, `_vid` |
| Simulation | `nepi_apps/nepi_app_nav_sim` |
| Device automation (drives PTX, consumes AI topics) | `nepi_apps/nepi_app_pan_tilt_auto` |
| Higher-level device manager | `nepi_apps/nepi_app_onvif_mgr` |

Also read the **Gotchas** section at the end of `APP_ARCHITECTURE.md` before your
first deploy.
