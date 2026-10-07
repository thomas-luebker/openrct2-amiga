"""Frame rate per park per machine, repeatably.

A frame rate is only meaningful attached to a view, and the view is what made every earlier attempt at
this useless: the old harness hunted for the built-up part of the map by colour and landed somewhere
different each run, so Heide Park read between 11 and 25 fps on one unchanged binary.

A .park file carries its own saved camera position, so loading one and never touching the view gives
the same picture every time on every machine. This does exactly that:
  * the pointer is parked mid-screen before the game opens, or the edge-scroll drags the view away;
  * the view is never moved afterwards;
  * whether a park loaded from the command line starts paused is NOT assumed -- clicking blind toggles
    it, and a paused game draws at the frame cap while simulating nothing, which read as 39 fps on a
    park that actually manages 18. The tick trace is used to check whether the simulation is advancing,
    the pause button is clicked only if it is not, and the check is repeated;
  * frames are then counted only over windows in which the simulation is still advancing.

  python3 fps.py PiStorm "Heide-Park.park" [--push]
"""
import os, re, statistics, sys, time
sys.path.insert(0, os.environ.get("AMIGA_FLEET_SCRIPTS") or os.path.expanduser("~/Development/AllAmigaTooling/skills/amiga-fleet/scripts"))
from fleet import connect
# Project root that holds build-68k/ next to the fork (the fork is <root>/upstream); override with OPENRCT2_AMIGA_ROOT.
PROJ = os.environ.get("OPENRCT2_AMIGA_ROOT") or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))

HOME = {"Amigo": "Work:OpenRCT2", "PiStorm": "Work:Games/OpenRCT2", "A4000": "Games:OpenRCT2Test/OpenRCT2"}
BIN = {"Amigo": "Work:OpenRCT2/openrct2", "PiStorm": "Work:Games/OpenRCT2/bin/openrct2",
       "A4000": "Games:OpenRCT2Test/OpenRCT2/bin/openrct2"}
RCT2 = {"Amigo": "Work:RCT2", "PiStorm": "Work:Games/RCT2", "A4000": "Games:OpenRCT2Test/RCT2"}

def click(a, x, y, wait=60):
    a.input_script([("move", x, y), ("wait", 5), ("button", "left", True), ("wait", 4),
                    ("button", "left", False), ("wait", wait)])

def quit_game(a):
    rc, out = a.exec_command("Status", timeout=90)
    if "openrct2" not in out.lower():
        return
    click(a, 83, 15, 50); click(a, 105, 203, 90); click(a, 320, 247, 150)
    for _ in range(25):
        time.sleep(6)
        rc, out = a.exec_command("Status", timeout=90)
        if "openrct2" not in out.lower():
            return
    raise SystemExit("could not quit the game")

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

def run(machine, park, do_push=False):
    home = HOME[machine]
    a = connect(machine, timeout=30, ignore_claim=True)
    quit_game(a)
    a.exec_command(f"Assign RCT2: {RCT2[machine]}", timeout=90)
    if do_push:
        push(a, os.path.join(PROJ, "build-68k", "openrct2"), BIN[machine])
    a.exec_command(f"Delete >NIL: {home}/fps-trace.txt", timeout=90)
    a.exec_command(f"SetEnv OPENRCT2_TRACE {home}/fps-trace.txt", timeout=60)
    a.exec_command("SetEnv OPENRCT2_NO_PEEPPROF 1", timeout=60)
    script = (f'cd {home}\n{BIN[machine]} "{home}/user/save/{park}" --rct2-data-path=RCT2: '
              f'--openrct2-data-path={home}/data --user-data-path={home}/user >{home}/fps.out\n')
    a.write_file(f"{home}/fps-run", script.encode())
    # park the pointer before the screen opens: left at an edge it scrolls the view for the whole load
    try:
        a.input_script([("move", 320, 240), ("wait", 2)])
    except Exception:
        pass
    a.exec_command(f"Run >NIL: Execute {home}/fps-run", timeout=90)

    t0 = time.time(); t = ""
    while time.time() - t0 < 3000:
        time.sleep(15)
        try:
            t = a.read_file(f"{home}/fps-trace.txt").decode("latin-1")
        except Exception:
            continue
        if "frame: per 20 draws" in t:
            break
    time.sleep(10)
    a.input_script([("move", 320, 240), ("wait", 2)])

    def ticking():
        """Is the simulation advancing? The tick line only appears when the game actually updates."""
        before = a.read_file(f"{home}/fps-trace.txt").decode("latin-1").count("tick: per 40 ticks")
        time.sleep(45)
        after = a.read_file(f"{home}/fps-trace.txt").decode("latin-1").count("tick: per 40 ticks")
        return after > before

    if not ticking():
        click(a, 8, 15, 60)                   # it was paused; this starts it
        if not ticking():
            raise SystemExit(f"{machine}: the simulation is not advancing, cannot measure a frame rate")

    t = a.read_file(f"{home}/fps-trace.txt").decode("latin-1")
    mark = len(t.splitlines())
    t0 = time.time()
    while time.time() - t0 < 900:
        time.sleep(20)
        t = a.read_file(f"{home}/fps-trace.txt").decode("latin-1")
        if len([x for x in t.splitlines()[mark:] if "gfx: 100 frames" in x]) >= 4:
            break
    new = t.splitlines()[mark:]
    # a window only counts if the game was still simulating through it
    if not [x for x in new if "tick: per 40 ticks" in x]:
        raise SystemExit(f"{machine}: the simulation stopped during the measurement")
    fps = [float(m) for m in re.findall(r"gfx: 100 frames in \d+ ms = ([\d.]+) fps",
                                        "\n".join(x for x in new if "gfx: 100 frames" in x))]
    heap = re.findall(r"heap: footprint (\d+) KB, in use (\d+) KB", "\n".join(new))
    guests = re.findall(r"(\d+) guests in park", "\n".join(new))
    fps_used = fps[1:4] if len(fps) >= 4 else fps          # drop the first, settling, window
    val = statistics.median(fps_used) if fps_used else None
    mem = (int(heap[-1][1]) // 1024, int(heap[-1][0]) // 1024) if heap else None
    print(f"{machine:8s} | {park:22s} | {val if val is not None else '-':>6} fps | "
          f"{guests[-1] if guests else '-':>5} guests | "
          f"{(str(mem[0]) + '/' + str(mem[1]) + ' MB') if mem else '-':>12s} | samples {fps}", flush=True)
    return val

if __name__ == "__main__":
    machine = sys.argv[1]
    parks = [x for x in sys.argv[2:] if not x.startswith("--")] or ["Heide-Park.park"]
    for i, park in enumerate(parks):
        run(machine, park, do_push=("--push" in sys.argv and i == 0))
