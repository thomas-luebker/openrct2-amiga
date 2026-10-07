"""Deterministic tick benchmark: time `openrct2-cli simulate` on real hardware.

The live-park benchmark measures whatever the park happens to be doing when the camera lands, and the
path-finding load alone varies threefold between runs. `simulate` runs a fixed park for a fixed number
of ticks with no drawing at all, so the wall clock is the simulation cost and the checksum proves the
run was identical. Use it for every before/after on the tick, and the live bench only for frame rate.

  python3 simbench.py PiStorm 600 [--push]

TWO TRAPS, both of which have produced a plausible wrong answer here:
  * The FIRST run on a park after the machine or emulator restarts also builds the object and scenario
    indexes and reads 30-60 % high. Discard it.
  * Run the binaries ALTERNATELY (a, b, a, b), never all of one and then all of the other, or the
    warm-up lands entirely on whichever went first and looks like a regression.
"""
import os, re, sys, time
sys.path.insert(0, os.environ.get("AMIGA_FLEET_SCRIPTS") or os.path.expanduser("~/Development/AllAmigaTooling/skills/amiga-fleet/scripts"))
from fleet import connect
# Project root that holds build-68k/ next to the fork (the fork is <root>/upstream); override with OPENRCT2_AMIGA_ROOT.
PROJ = os.environ.get("OPENRCT2_AMIGA_ROOT") or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))

# home directory of the game, default park, and where the RCT2 data lives. `simulate` takes no options,
# so the data has to be reachable through the platform's own search list -- "RCT2:" is on it, which is
# why the assign is made before every run.
PATHS = {
    "PiStorm": ("Work:Games/OpenRCT2", "Work:Games/OpenRCT2/user/save/Heide-Park.park", "Work:Games/RCT2"),
    "A4000":   ("Games:OpenRCT2Test/OpenRCT2", "Games:OpenRCT2Test/OpenRCT2/user/save/cc-old.park",
                "Games:OpenRCT2Test/RCT2"),
    "Amigo":   ("Work:OpenRCT2", "Work:OpenRCT2/user/save/cc-old.park", "Work:RCT2"),
}

def push(a, local, remote):
    data = open(local, "rb").read(); CH = 4*1024*1024; parts = []
    for i in range(0, len(data), CH):
        p = f"{remote}.p{i//CH}"; a.write_file(p, data[i:i+CH]); parts.append(p)
    a.exec_command(f"Delete >NIL: {remote}", timeout=120)
    a.exec_command("Join " + " ".join(parts) + f" AS {remote}", timeout=600)
    for p in parts: a.exec_command(f"Delete >NIL: {p}", timeout=60)
    a.exec_command(f"Protect {remote} +e", timeout=60)
    rc, out = a.exec_command(f"List {remote} LFORMAT %L", timeout=60)
    assert out.strip() == str(len(data)), f"size mismatch {out.strip()} vs {len(data)}"
    print(f"cli pushed ({len(data)} bytes)", flush=True)

def run(machine, ticks, park=None, do_push=False, env=None,
        cli=os.path.join(PROJ, "build-68k", "openrct2-cli")):
    home, defaultPark, rct2 = PATHS[machine]
    park = park or defaultPark
    a = connect(machine, timeout=30, ignore_claim=True)
    rc, out = a.exec_command("Status", timeout=60)
    if "openrct2" in out.lower():
        raise SystemExit("something of the game is still running:\n" + out)
    if do_push:
        push(a, cli, f"{home}/openrct2-cli")
    # With no --user-data-path the CLI uses PROGDIR:user and the environment appends OpenRCT2 to it, so
    # the config it reads is NOT the one the UI is launched with. Make sure that one names the RCT2 data.
    cfgPath = f"{home}/user/OpenRCT2/config.ini"
    try:
        cfg = a.read_file(cfgPath).decode("latin-1")
    except Exception:
        cfg = ""
    if f'game_path = "{rct2}"' not in cfg:
        import re as _re
        if "game_path" in cfg:
            cfg = _re.sub(r'game_path = "[^"]*"', f'game_path = "{rct2}"', cfg)
        else:
            cfg = ("[general]\n" if not cfg else cfg) + f'game_path = "{rct2}"\n'
        a.write_file(cfgPath, cfg.encode("latin-1"))
        print(f"set game_path in {cfgPath}", flush=True)
    a.exec_command(f"Delete >NIL: {home}/sim.out", timeout=60)
    # `simulate` takes no options, so the data paths have to come from the config: cd into the game
    # directory first so PROGDIR: and the current directory both point at it, exactly as run-sim does.
    script = f"cd {home}\n{home}/openrct2-cli simulate \"{park}\" {ticks} >{home}/sim.out\n"
    a.write_file(f"{home}/simbench-run", script.encode("latin-1"))
    for k in ("OPENRCT2_TRACE", "OPENRCT2_NO_PEEPPROF", "OPENRCT2_PAINT_PROF"):
        a.exec_command(f"UnSetEnv {k}", timeout=30)
    for k, v in (env or {}).items():
        a.exec_command(f"SetEnv {k} {v}", timeout=30)
    a.exec_command(f"Run >NIL: Execute {home}/simbench-run", timeout=60)
    t0 = time.time()
    while time.time() - t0 < 3600:
        time.sleep(10)
        rc, out = a.exec_command("Status", timeout=60)
        if "openrct2-cli" not in out.lower():
            break
    wall = time.time() - t0
    txt = a.read_file(f"{home}/sim.out").decode("latin-1")
    m = re.findall(r"Completed:\s*([0-9a-f]{16,})", txt)
    digest = m[-1][:16] if m else None
    print(f"{machine}: {ticks} ticks of {park.split('/')[-1]} in {wall:.0f} s "
          f"({wall*1000.0/ticks:.1f} ms per tick), checksum {digest}", flush=True)
    if digest is None:
        print(txt[-500:], flush=True)
    trace = (env or {}).get("OPENRCT2_TRACE")
    if trace:
        try:
            t = a.read_file(trace).decode("latin-1")
            for pat in ("tick: per 40 ticks", "guest update ms", "pathfind:", "heap: footprint"):
                for line in [x for x in t.splitlines() if pat in x][-2:]:
                    print("   ", line[:300], flush=True)
        except Exception as e:
            print("   (no trace:", str(e)[:80], ")", flush=True)
    return wall, digest

if __name__ == "__main__":
    machine = sys.argv[1]
    ticks = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 600
    env = {}
    for a_ in sys.argv[3:]:
        if "=" in a_ and not a_.startswith("--"):
            k, _, v = a_.partition("="); env[k] = v or "1"
    run(machine, ticks, do_push="--push" in sys.argv, env=env)
