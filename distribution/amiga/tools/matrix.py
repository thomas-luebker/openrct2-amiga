"""Benchmark one machine across several parks and print a row per park.

Deterministic: `openrct2-cli simulate` runs a fixed park for a fixed number of ticks with no drawing
and prints a checksum, so the same work is timed on every machine and the checksum proves it was the
same work.

THE TIME IS MEASURED AS A SLOPE, and it has to be. The wall clock of one `simulate` run is dominated
by start-up -- loading the objects takes 20-35 s, while 600 ticks of a small park take a couple of
seconds -- so dividing total time by tick count measures the loader, not the simulation. It gave the
emulator and a PiStorm the same 51.9 ms "per tick" for the same park on 2026-09-17, which is what
exposed it. Running the same park at two tick counts and taking the difference cancels the start-up
exactly, and the leftover intercept is the load time, which is worth having anyway.

Two further traps this obeys:
  * the FIRST run of a park on a machine also builds the object and scenario indexes and reads high,
    so a discarded warm-up runs first;
  * the trace costs about 20 ms a tick on a PiStorm, so it is on for the warm-up, which is where the
    guest count comes from, and off for both timed runs.

  python3 matrix.py PiStorm [--push]

Run the three machines concurrently -- they are independent, and the A4000 takes far longer than the
emulator.
"""
import os, re, sys, time
sys.path.insert(0, os.environ.get("AMIGA_FLEET_SCRIPTS") or os.path.expanduser("~/Development/AllAmigaTooling/skills/amiga-fleet/scripts"))
from fleet import connect
# Project root that holds build-68k/ next to the fork (the fork is <root>/upstream); override with OPENRCT2_AMIGA_ROOT.
PROJ = os.environ.get("OPENRCT2_AMIGA_ROOT") or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))

HOME = {"Amigo": "Work:OpenRCT2", "PiStorm": "Work:Games/OpenRCT2", "A4000": "Games:OpenRCT2Test/OpenRCT2"}
CLI = {"Amigo": "Work:OpenRCT2/openrct2-cli", "PiStorm": "Work:Games/OpenRCT2/openrct2-cli",
       "A4000": "Games:OpenRCT2Test/OpenRCT2/openrct2-cli"}
RCT2 = {"Amigo": "Work:RCT2", "PiStorm": "Work:Games/RCT2", "A4000": "Games:OpenRCT2Test/RCT2"}
# Tick counts per park, low and high. The spread has to be wide enough that the difference between the
# two runs is large next to the polling resolution: a near-empty park costs so little per tick that
# 300 against 1500 ticks differs by a few milliseconds and measures nothing.
PARKS = [("cc-old.park", 500, 20000),
         ("Extreme Heights.park", 500, 10000),
         ("Heide-Park.park", 300, 2000)]

def push(a, local, remote):
    data = open(local, "rb").read(); CH = 4 * 1024 * 1024; parts = []
    for i in range(0, len(data), CH):
        q = f"{remote}.p{i//CH}"; a.write_file(q, data[i:i+CH]); parts.append(q)
    a.exec_command(f"Delete >NIL: {remote}", timeout=180)
    a.exec_command("Join " + " ".join(parts) + f" AS {remote}", timeout=900)
    for q in parts:
        a.exec_command(f"Delete >NIL: {q}", timeout=120)
    a.exec_command(f"Protect {remote} +e", timeout=90)
    rc, out = a.exec_command(f"List {remote} LFORMAT %L", timeout=90)
    assert out.strip() == str(len(data)), f"size mismatch {out.strip()} vs {len(data)}"

def one(a, machine, park, ticks, trace):
    home = HOME[machine]
    a.exec_command(f"Delete >NIL: {home}/mx.out", timeout=90)
    a.exec_command(f"Delete >NIL: {home}/mx-trace.txt", timeout=90)
    if trace:
        a.exec_command(f"SetEnv OPENRCT2_TRACE {home}/mx-trace.txt", timeout=60)
    else:
        a.exec_command("UnSetEnv OPENRCT2_TRACE", timeout=60)
    path = f'{home}/user/save/{park}'
    a.write_file(f"{home}/mx-run",
                 f'cd {home}\n{CLI[machine]} simulate "{path}" {ticks} >{home}/mx.out\n'.encode())
    t0 = time.time()
    a.exec_command(f"Run >NIL: Execute {home}/mx-run", timeout=90)
    while time.time() - t0 < 5400:
        time.sleep(2)
        rc, out = a.exec_command("Status", timeout=60)
        if "openrct2-cli" not in out.lower():
            break
    wall = time.time() - t0
    txt = a.read_file(f"{home}/mx.out").decode("latin-1")
    m = re.findall(r"Completed:\s*([0-9a-f]{16,})", txt)
    guests = mem = None
    if trace:
        try:
            tr = a.read_file(f"{home}/mx-trace.txt").decode("latin-1")
            gs = re.findall(r"(\d+) guests in park", tr)
            if gs:
                guests = int(gs[-1])
            ms = re.findall(r"mem: after s6 init: in use (\d+) KB, footprint (\d+) KB", tr)
            if ms:
                mem = (int(ms[-1][0]) // 1024, int(ms[-1][1]) // 1024)
        except Exception:
            pass
    return wall, (m[-1][:16] if m else None), guests, mem

if __name__ == "__main__":
    machine = sys.argv[1]
    a = connect(machine, timeout=30, ignore_claim=True)
    rc, out = a.exec_command("Status", timeout=90)
    assert "openrct2" not in out.lower(), f"{machine}: something of the game is still running"
    a.exec_command(f"Assign RCT2: {RCT2[machine]}", timeout=90)
    if "--push" in sys.argv:
        push(a, os.path.join(PROJ, "build-68k", "openrct2-cli"), CLI[machine])
        print(f"{machine}: cli pushed", flush=True)
    for park, n_low, n_high in PARKS:
        # warm the indexes and read the guest count; this run's time is not used
        _, _, guests, _ = one(a, machine, park, n_low, trace=True)
        t_low, d_low, _, _ = one(a, machine, park, n_low, trace=False)
        t_high, d_high, _, _ = one(a, machine, park, n_high, trace=False)
        per_tick = (t_high - t_low) * 1000.0 / (n_high - n_low)
        startup = t_low - n_low * per_tick / 1000.0
        print(f"{machine:8s} | {park:22s} | {per_tick:7.2f} ms/tick | {startup:5.0f} s to load | "
              f"{guests if guests is not None else '-':>5} guests | {d_low} {d_high}", flush=True)
