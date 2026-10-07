# Release gate and benchmarks

These scripts decide whether a 68k build can go out to testers. Each one drives a real or emulated
Amiga through [amiagent](https://github.com/thomas-luebker/amiagent) and its Python client `fleet.py`.
They run on the Mac that cross-builds the game.

The bar for a test build: **parity** must match, the **release check** and the **soak** must pass, and
the **leak check** must show 0 MB. All of them run on the exact binary that ships, and the build is
then confirmed on real hardware.

| Script | What it answers | Run |
|---|---|---|
| `parity.py` | Is the 68k simulation still bit-exact? Three reference `.park` checksums on the 68k CLI. | `python3 parity.py [openrct2-cli]` |
| `release_check.py` | Sound, start-up time, frame rate, scrolling and tick cost on the Amigo emulator. Prints PASS/FAIL. | `python3 release_check.py <openrct2>` |
| `soak.py` | Does memory drift over repeated park loads, a crowded park and continuous scrolling? | `python3 soak.py [openrct2]` |
| `leak_check.py` | Is memory given back to the system on exit? AmigaOS reclaims nothing on its own. | `python3 leak_check.py [machine] [--push]` |
| `simbench.py` | Tick cost on one machine, with no drawing, plus a checksum. Use it for every before/after on the simulation. | `python3 simbench.py <machine> <ticks> [--push]` |
| `matrix.py` | Tick cost and load time across several parks on one machine, measured as a slope so start-up cancels out. | `python3 matrix.py <machine> [--push]` |
| `fps.py` | Frame rate per park from the park's own saved camera, so it can be repeated. | `python3 fps.py <machine> [--push]` |
| `repaint_check.py` | Does a dirty-block repaint match a full one, pixel for pixel? | `REPAINT_OUT=dir python3 repaint_check.py <tag>` |
| `guest.py`, `shot.py` | Helpers: restart and drive the Amigo emulator, save the RTG screen as a PNG. | (imported by the scripts) |

Each script's docstring explains how it measures and the traps it works around. Read it before
trusting a number. The biggest trap: **a machine's first `simulate` run on a park also builds the
object and scenario indexes and reads 30–60 % high, so discard it.**

## Setup

- `fleet.py` comes from the amiga-fleet tooling, loaded from
  `~/Development/AllAmigaTooling/skills/amiga-fleet/scripts`. Point `AMIGA_FLEET_SCRIPTS` somewhere
  else to override that.
- `--push` and the default binary paths assume the project layout this fork was built in: the fork at
  `<root>/upstream` and the builds at `<root>/build-68k`. Set `OPENRCT2_AMIGA_ROOT` to use another
  root.
- The machine names (`Amigo`, `PiStorm`, `A4000`) and their AmigaOS paths (`Work:OpenRCT2`, …) are
  set in tables at the top of each script. Change them for your own machines.
