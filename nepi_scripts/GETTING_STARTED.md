# Getting Started - Creating & Deploying a NEPI Automation Script

This is the practical workflow for turning a script template into a running
automation script on a NEPI device. For *how scripts work* (scripts_mgr,
launch/stop rules, monitoring), read `SCRIPT_STRUCTURE.md`.

Scripts are the fastest NEPI extension point: a single `.py` file copied to
the device is discovered within a second. No build, no restart.

---

## 1. Pick a shape

| You want... | Start from |
|---|---|
| Something that runs continuously until stopped (polling, bridging, mission logic, watching topics) | `template_script_node.py` |
| Something that does one job and exits (housekeeping, a one-shot command sequence, an external API call) | `template_script_task.py` |

## 2. Create your script from the template

1. **Copy the template file** into your own repo/location, along with
   `deploy_nepi_scripts.sh` sitting next to it.
2. **Rename the file.** The filename IS the script's identity: it is what
   the Scripts Manager page lists, what the log file is named after, and
   what the launch/stop services take as an argument. Convention:
   `<something>_node.py` for the node shape, plain `<something>.py` for
   tasks.
3. For the node shape, also rename the class, `DEFAULT_NODE_NAME`, and every
   `script_template` / `ScriptTemplate` token.
4. **Fill in the TODOs:**
   - *node shape* - your settings in `PARAMS_DICT`, your control topics in
     `SUBS_DICT`, your work in `updaterCb`, your status fields in
     `publish_status`. For worker threads, device control, image publishing,
     and discovery patterns, crib from `../nepi_apps/APP_PATTERNS.md`; the
     node skeleton is the same one apps use.
   - *task shape* - your arguments in `main()`, your work in `run_task()`.
     Keep the SIGTERM stop-check and return meaningful exit codes (0 =
     success; the RUI counts anything else as an errored run).
5. **Keep the shebang line.** The file is executed directly; without
   `#!/usr/bin/env python` it will not launch.
6. **Syntax-check:**
   ```bash
   python3 -m py_compile my_script_node.py
   ```

## 3. Deploy

`deploy_nepi_scripts.sh` copies script files to the folder `scripts_mgr`
watches on the target:

```
/mnt/nepi_storage/nepi_scripts/
```

Usage:

```bash
export NEPI_REMOTE_SETUP=0          # 0 = running on the target, 1 = from a dev host
./deploy_nepi_scripts.sh                    # deploy every .py next to the script
./deploy_nepi_scripts.sh my_script_node.py  # or just one
```

Remote mode (`NEPI_REMOTE_SETUP=1`) additionally needs `NEPI_TARGET_IP`
(taken from `NEPI_IP`) and the default SSH key at
`~/ssh_keys/nepi_engine_default_private_ssh_key`.

There is no build step. Any copy method works (scp, a network share, a USB
stick); the deploy script is just the convenient one. Do NOT put anything
except runnable scripts in that folder: every file in it is treated as a
launchable script.

## 4. Run and watch

1. Open the **Scripts Manager** page in the RUI (same page selector as the
   Drivers and Apps managers). Your file appears within a second of landing
   in the folder.
2. Select it and press **Start**. Optional: set its **cmd line args** and
   the **auto-start** checkbox (launches it whenever NEPI boots).
3. Watch the log:
   ```bash
   tail -f /mnt/nepi_storage/logs/nepi_scripts_logs/<your_filename>.log
   ```
4. Node-shape scripts: check the status topic from any console:
   ```bash
   rostopic echo /nepi/<device_id>/<node_name>/status
   ```
5. Iterate: edit the file, redeploy, **Stop and Start the script** (an edit
   does not restart a running instance).

## Reference scripts to crib from

| Your script is like... | Read |
|---|---|
| Poll an external service / device and publish results | `template_script_node.py` (this shape, filled in: see any `*_node.py` deployed in `/mnt/nepi_storage/nepi_scripts/` on a configured device) |
| Bridge / transform between ROS topics | node shape + `../nepi_apps/APP_PATTERNS.md` Section 3 (discovery) |
| Command a NEPI device (PTX, camera) on a schedule | node shape + `APP_PATTERNS.md` Section 5 (`Connect*` classes) |
| One-shot job with arguments | `template_script_task.py` |

Also read the **Gotchas** section at the end of `SCRIPT_STRUCTURE.md` before
your first deploy.
