# nepi_templates

Copy-paste starting points for extending a NEPI device. Each top-level folder
matches an extension point of the NEPI engine and contains working, tested
template code plus two docs: a `*_STRUCTURE.md` explaining how that part of
the system works, and a `GETTING_STARTED.md` with the practical
create/deploy workflow.

```
nepi_templates/
├── nepi_drivers/                 # hardware support (one template per driver type)
│   ├── idx_template/             #   imaging devices (cameras)
│   ├── lsx_template/             #   lights
│   ├── ptx_template/             #   pan/tilt units
│   ├── npx_template/             #   navigation / position devices
│   ├── rbx_template/             #   robots / autopilots
│   ├── deploy_nepi_drivers.sh
│   ├── DRIVER_STRUCTURE.md
│   └── GETTING_STARTED.md
│
├── nepi_apps/                    # full apps (node + config + RUI page)
│   ├── nepi_app_template/        #   complete catkin app package
│   ├── deploy_nepi_apps.sh
│   ├── APP_STRUCTURE.md
│   ├── APP_PATTERNS.md           #   add-on patterns with real code excerpts
│   └── GETTING_STARTED.md
│
└── nepi_scripts/                 # automation scripts (single .py files)
    ├── template_script_node.py   #   long-running script (runs until stopped)
    ├── template_script_task.py   #   run-once script (does a job, exits)
    ├── deploy_nepi_scripts.sh
    ├── SCRIPT_STRUCTURE.md
    └── GETTING_STARTED.md
```

## Which template do I need?

| You want to... | Use | Effort |
|---|---|---|
| Add glue logic, an external integration, a mission, or a one-shot job | `nepi_scripts/` | Lightest: one file, no build, discovered in ~1 second |
| Build a capability with its own RUI page, config, and custom msgs | `nepi_apps/` | Catkin package + workspace build + RUI rebuild |
| Add support for a new hardware device | `nepi_drivers/` | Catkin files + workspace build; pick the template for your device type |

When unsure, start with a script and graduate to an app when you need a
custom RUI page or custom message types.

## How to use (all template types)

1. **Copy the template you want into your own repo**, along with the
   `deploy_*.sh` script sitting next to it. Don't develop inside this repo;
   it stays clean as the reference.
2. **Rename** the folder/files and every `template` token, following the
   rename checklist in that folder's `GETTING_STARTED.md` (names must stay
   consistent across specific files or discovery silently fails).
3. **Fill in the TODOs.** Templates run as-is; every place that needs your
   code is marked `TODO`.
4. **Deploy** with the folder's deploy script. All deploy scripts share the
   same convention:
   ```bash
   export NEPI_REMOTE_SETUP=0   # 0 = running on the target, 1 = from a dev host
   ./deploy_nepi_<type>.sh      # no args = deploy everything next to the script
   ./deploy_nepi_<type>.sh x y  # or a subset
   ```
   Remote mode (`NEPI_REMOTE_SETUP=1`) also needs `NEPI_IP` set and the
   default NEPI SSH key at `~/ssh_keys/nepi_engine_default_private_ssh_key`.
5. **Build if needed.** Drivers and apps go into the engine source tree and
   need a workspace rebuild (apps with a RUI page also need the RUI
   rebuild). Scripts need no build at all: they are discovered within a
   second of landing on the device.

Each `GETTING_STARTED.md` expands these steps for its template type, and
each `*_STRUCTURE.md` explains the machinery underneath (managers,
discovery, interfaces, gotchas). Read the Gotchas section of the relevant
structure doc before your first deploy.
