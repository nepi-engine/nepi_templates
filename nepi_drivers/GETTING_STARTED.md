# Getting Started — Creating & Deploying a NEPI Driver from a Template

This is the practical workflow for turning one of the templates in this folder
into a real driver and getting it onto a NEPI device. For *how drivers work*
(discovery models, the launch handshake, the interface-class contract), read
`DRIVER_ARCHITECTURE.md`.

---

## 1. Create your driver from a template

1. **Copy the template folder** matching your device type (e.g. `idx_template/`)
   into your own repo/location, **along with `deploy_nepi_drivers.sh`**.
   Keep the folder named `<cat>_template/` and sitting next to the script —
   that is where the deploy script looks for it. `setup_new_driver.sh` rides
   along inside the folder.
2. **Rename everything with `setup_new_driver.sh`** (recommended). Edit the
   EDIT-THESE block at the top of `<cat>_template/setup_new_driver.sh`
   (`DRIVER_NAME`, `DISPLAY_NAME`, `DESCRIPTION`, and optional `CLASS_BASE`),
   then run it from inside the folder:

   ```bash
   cd idx_template
   ./setup_new_driver.sh --dry-run   # preview the rename plan
   ./setup_new_driver.sh             # do it (renames the files + tokens)
   ```

   It auto-detects the category from the folder name and renames every
   `<cat>_template_*` file plus the `pkg_name`/`PKG_NAME`, class names, and the
   matching `NODE_DICT`/`DRIVER_DICT`/`DISCOVERY_DICT` yaml entries together, so
   they stay in lock-step. `DRIVER_NAME` (snake_case, e.g. `deepsea_sealite`)
   becomes the file prefix + `pkg_name`; set `CLASS_BASE` (e.g. `Sealite`) for
   shorter class names. The **folder is left named `<cat>_template/`** on
   purpose (that is what the deploy script globs), and comments that reference
   the sibling templates are left intact. Delete the script once you have run
   it.

   <details><summary>Or rename by hand — the token checklist</summary>

   Rename every `template` / `Template` token to your device across all files:
   file names, `pkg_name`, `PKG_NAME`, and the class names. Keep the
   `NODE_DICT`/`DRIVER_DICT`/`DISCOVERY_DICT` `file_name`/`class_name` entries in
   the yaml matching the real files/classes **exactly** (mismatches are a common
   silent failure).

   </details>
3. **Fill the `TODO:` markers:**
   - *discovery* — your enumeration + a real `checkForDevice` handshake, and the
     `DEVICE_DICT` fields your node needs.
   - *node* — the capability callbacks for your interface class, and (if serial)
     your `send_msg` protocol; (if IDX) your driver ctor call.
   - *driver* (IDX only) — the real hardware I/O against your SDK.
   - *params* — `display_name`, `description`, and the `OPTIONS` your discovery
     reads.
4. **Syntax-check:** `python3 -m py_compile <your files>.py` and
   `python3 -c "import yaml; yaml.safe_load(open('...params.yaml'))"`.

---

## 2. Deploy to the NEPI src tree

`deploy_nepi_drivers.sh` handles the "flatten into the right place" step for
you. It rsyncs **only the `.py` and `.yaml` files** (no docs, scripts, or
`__pycache__`) from each `<cat>_template/` folder flat into the target's
source tree at:

```
${NEPI_TARGET_SRC_DIR}/nepi_engine_ws/src/nepi_drivers/<cat>_drivers/
```

(Drivers must live **flat** in `<cat>_drivers/` — not in per-driver subfolders.
See `DRIVER_ARCHITECTURE.md` Section 7 for why.)

Usage:

```bash
export NEPI_REMOTE_SETUP=0          # 0 = running on the target, 1 = from a dev host
./deploy_nepi_drivers.sh            # deploy ALL template types
./deploy_nepi_drivers.sh idx        # deploy just the idx template
./deploy_nepi_drivers.sh idx ptx    # or any subset by category
```

Remote mode (`NEPI_REMOTE_SETUP=1`) additionally needs `NEPI_TARGET_IP` (taken
from `NEPI_IP`) and the default SSH key at
`~/ssh_keys/nepi_engine_default_private_ssh_key`; it then rsyncs over SSH the
same way.

> Shell-scripting note: the rsync filters are passed as a **quoted bash array**
> (`RSYNC_FILTERS=(--include '*.py' ... --exclude '*')`). Keeping them in an
> unquoted string variable breaks badly — the shell glob-expands `*` into the
> current directory's filenames, which become extra rsync *source* arguments
> and junk gets copied to the target.

---

## 3. Build & watch it come up

After deploying, **rebuild the workspace** so the files install to
`/opt/nepi/nepi_engine/lib/nepi_drivers/` where `drivers_mgr` scans them. Then
watch the `drivers_mgr` log — it prints when it imports/launches discovery and
when a device node comes up.

---

## Reference drivers to crib from

| Your device is like… | Read the shipped driver |
|---|---|
| USB / V4L2 camera | `idx_drivers/idx_v4l2_*` |
| GigE / SDK camera | `idx_drivers/idx_genicam_*` |
| Serial light | `lsx_drivers/lsx_deepsea_sealite_*` |
| Serial pan-tilt | `ptx_drivers/ptx_sidus_ss109_serial_*` |
| Network navpose (NMEA/TCP) | `npx_drivers/npx_nmea_udp_*` |
| Serial IMU (vendor ROS driver) | `npx_drivers/npx_microstrain_*` |
| Autopilot / vehicle | `rbx_drivers/rbx_ardupilot_*` |

Also read the **Gotchas** section at the end of `DRIVER_ARCHITECTURE.md` before
your first bench test.
