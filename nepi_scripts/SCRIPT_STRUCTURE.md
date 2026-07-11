# NEPI Automation Scripts - How They Work

This folder holds templates for NEPI automation scripts: single Python files
that live in `/mnt/nepi_storage/nepi_scripts/` on a NEPI device and are
managed by the `scripts_mgr` node (launch, stop, monitor, auto-start). For
the create/deploy workflow, read `GETTING_STARTED.md`.

```
nepi_scripts/
├── template_script_node.py   <- long-running script (full NEPI node, runs until stopped)
├── template_script_task.py   <- run-once script (does a job, exits with a return code)
├── deploy_nepi_scripts.sh    <- copies scripts to the device scripts folder
├── SCRIPT_STRUCTURE.md       <- this file
└── GETTING_STARTED.md        <- practical workflow
```

---

## 1. The big picture: script vs app vs driver

A script is the lightest way to add behavior to a NEPI device:

| | Automation script | App | Driver |
|---|---|---|---|
| What it is | one `.py` file in a storage folder | catkin package (node/params/msg/api/rui) | catkin package implementing a device IF |
| Install | file copy, discovered in ~1 second | deploy + workspace build + RUI rebuild | deploy + workspace build |
| Custom ROS msgs | no (std_msgs / nepi_interfaces only) | yes | yes |
| Own RUI page | no (managed from the Scripts Manager page) | yes | via device pages |
| Launched by | `scripts_mgr` (direct process exec) | `apps_mgr` (rosrun) | `drivers_mgr` / discovery |
| Best for | glue logic, external integrations, missions, one-shot jobs, fast iteration | polished capability with UI | hardware support |

Start as a script; graduate to an app when you need a custom RUI page or
custom message types.

## 2. How scripts_mgr manages your file

`scripts_mgr` (in `nepi_engine/nepi_managers`) watches the scripts folder:

- **Folder**: `/mnt/nepi_storage/nepi_scripts/` (resolved from the system
  user folders config; that path is the standard location). **Every
  non-directory file in it is treated as a script**, so keep data files,
  READMEs, and libraries out of this folder.
- **Discovery**: the folder is polled every second by modification time. A
  new or edited file is picked up within ~1 s, gets `dos2unix` run on it
  (Windows line endings won't break you), and has its run counters reset.
  No restart of anything is needed.
- **Launch** (RUI Start button or the `launch_script` service):
  1. `chmod 774` on the file.
  2. The file is executed **directly** (`Popen` on the file itself, not
     `python file`), so the `#!/usr/bin/env python` shebang selects the
     interpreter. A file without a shebang fails to launch.
  3. The per-script **cmd line args** config string is split on whitespace
     and passed as argv (see `template_script_task.py`'s argparse).
  4. Environment is inherited from the NEPI engine (full ROS env available)
     plus `PYTHONUNBUFFERED=on`.
  5. stdout and stderr are piped, line-buffered, to
     `/mnt/nepi_storage/logs/nepi_scripts_logs/<filename>.log`. `print()`
     and `MsgIF` output both land there, live.
- **One instance**: a script already running will not be launched again.
- **Stop** (RUI Stop button or `stop_script` service): the process gets
  SIGTERM, then **SIGKILL after 10 seconds** (`script_stop_timeout_s`).
  Your script has 10 s to clean up and exit.
- **Exit accounting**: exit code 0 increments the script's "completed"
  counter; anything else increments "errored out". These counters, plus
  CPU/memory/run-time stats, show in the Scripts Manager page (served by the
  `get_system_stats` service).
- **Auto-start**: per-script flag, toggled from the Scripts Manager page
  (or the `enable_script_autostart` topic, `AutoStartEnabled` msg). It is
  persisted with the saved config, and flagged scripts are launched when
  `scripts_mgr` starts on boot.

Manager services live at the base namespace: `get_scripts`,
`get_running_scripts`, `launch_script`, `stop_script`, `get_system_stats`.

## 3. The two script shapes

### Node shape (`template_script_node.py`)

A full NEPI node in a single file: it calls `nepi_sdk.init_node()` itself
(scripts are standalone processes, nothing rosruns them), builds a
`NodeClassIF` with params/pubs/subs under its own namespace, and spins until
stopped. You get for free:

- **Persistent settings** through the NEPI config system (`set_param` +
  `save_config`, restored by `initCb` on next launch), identical to apps.
- **Control topics** other nodes or the console can publish to
  (`set_enabled`, `set_update_rate`, plus whatever you add).
- **A latched `status` topic.** Since scripts can't define custom msg types,
  the working pattern is a JSON dict in a `std_msgs/String` (echo it with
  `rostopic echo <base_namespace>/<node_name>/status`).
- **Clean shutdown**: rospy converts the SIGTERM from Stop into a normal
  ROS shutdown, so `cleanup_actions` runs and `spin()` returns, well inside
  the 10 s window (as long as your cleanup is fast).

The node body is the same skeleton apps use, so all the add-on patterns in
`../nepi_apps/APP_PATTERNS.md` apply directly: worker threads, periodic
resource discovery, driving devices with `Connect*` classes, publishing
images or navpose through the `nepi_api` data classes.

### Task shape (`template_script_task.py`)

A plain Python program: parse argv, do the job, `sys.exit(code)`. No ROS at
all unless you add it. The template demonstrates the three things every task
script should have:

- **argparse**, because the per-script cmd line args config arrives as argv.
- **A SIGTERM handler** setting a stop flag that the work loop checks, so a
  Stop from the RUI aborts cleanly instead of being SIGKILLed mid-write.
- **Meaningful exit codes**, because they are the success/fail report shown
  in the Scripts Manager counters.

If a task needs ROS (e.g. trigger a snapshot then exit), call
`nepi_sdk.init_node()` at the start of `main()` and use the `nepi_api`
`Connect*` classes; the rest of the shape stays the same.

## 4. Monitoring and control surfaces

- **RUI**: the **Scripts Manager** page (in the same selector as Drivers
  Manager / Apps Manager) lists every file in the scripts folder with
  Start/Stop, the auto-start checkbox, and live stats: CPU %, memory %, run
  time, file size, log size, started/completed/errored/stopped counters.
- **Logs**: `/mnt/nepi_storage/logs/nepi_scripts_logs/<filename>.log`,
  overwritten on each launch. `tail -f` it while developing.
- **Programmatic**: the base-namespace services listed in Section 2 let
  other nodes (or another script) launch and stop scripts.

## 5. Gotchas

- **Everything in the folder is a "script".** A stray README, data file, or
  imported helper module in `/mnt/nepi_storage/nepi_scripts/` shows up as a
  launchable script in the RUI. Scripts must be self-contained single files;
  shared logic belongs in an installed package (e.g. `nepi_sdk`), not in a
  sibling file.
- **No shebang, no launch.** The file is executed directly; the first line
  must be `#!/usr/bin/env python` (or `python3`).
- **Exit within 10 s of SIGTERM** or be SIGKILLed. Node-shape scripts get
  this for free via rospy; task-shape scripts need the signal handler.
- **Editing a running script does not restart it.** The old process keeps
  running the old code; stop and re-start it. The edit does reset the
  script's run counters (mtime change = "new script" to the manager).
- **cmd line args are split on whitespace only.** No shell quoting: an
  argument value cannot contain spaces.
- **No custom msg types.** Use `std_msgs` / `nepi_interfaces` types, or JSON
  in a String for structured data.
- **Log file is overwritten each launch.** Copy it aside if you need the
  previous run's output.
- **Long-lived scripts should throttle their warns.** A failing poll loop
  writes to its log every cycle forever; use
  `msg_if.pub_warn(..., throttle_s=10)` like the template does.
