"""Release check on the Amigo guest: sound, performance, scrolling. Prints a PASS/FAIL summary.

    python3 release_check.py <path to 68k openrct2 binary>

Scenes (each a fresh guest): title screen (AHI open, load time, fps, audio health), audio dump (mixed
stream is not silent), Crazy Castle (static fps, scrolling fps, blit sanity), Kahuna Point (tick cost with
1,560 guests). Thresholds are for the Amigo 68040 emulator on a mostly idle Mac.
"""
import os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guest import fresh_game, wait_trace

BIN = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None
results = []


def check(name, ok, detail):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}", flush=True)


def fps_of(line):
    m = re.search(r"= (\d+)\.(\d+) fps", line)
    return float(m.group(1) + "." + m.group(2)) if m else 0.0


# 1. Title screen ------------------------------------------------------------------------------
print("[1/4] title screen", flush=True)
a = fresh_game(BIN, "Work:OpenRCT2/run-ui-rc")  # like run-ui, but records the program's return code in rc.txt
t = wait_trace(a, lambda t: t.count("gfx: 100") >= 3, limit=420)
lines = t.splitlines()
ahi = [l for l in lines if "audio: AHI opened" in l]
check("AHI opened", bool(ahi), ahi[0][ahi[0].index("audio"):][:60] if ahi else "no 'audio: AHI opened' line")
obj = [l for l in lines if "objects:" in l and "required loaded" in l]
if obj:
    ms = int(re.search(r"loaded in (\d+) ms", obj[0]).group(1))
    check("title objects load", ms < 40000, f"{ms} ms for the title park's objects")
else:
    check("title objects load", False, "no objects line")
first = [l for l in lines if "title: park prepared" in l]
if first:
    ms = int(re.search(r"\[\+(\d+)ms\]", first[0]).group(1))
    check("time to title", ms < 90000, f"{ms / 1000:.0f} s from start to the title park")
gfx = [l for l in lines if "gfx: 100" in l]
f = fps_of(gfx[-1]) if gfx else 0
check("title fps", f >= 20, f"{f} fps on the title park")
# audio health: one line per 1000 AHI requests (46-743 ms each). It must appear: since the double-buffering fix
# the emulator plays continuously; underruns happen only while a park loads.
# The request length adapts to the loop's pace (46-743 ms), so 1000 requests take 46 s on an idle host and up to
# several minutes under host load or while parks load: allow ten minutes.
t = wait_trace(a, lambda t: "buffers written" in t, limit=600, step=10)
health = [l for l in t.splitlines() if "buffers written" in l]
if health:
    w, u = re.search(r"(\d+) buffers written, (\d+) underruns", health[-1]).groups()
    check("audio health", int(u) <= int(w) // 20, f"{w} buffers written, {u} underruns")
else:
    check("audio health", False, "no 'buffers written' line within 10 minutes: AHI playback stalled")
# clean exit: the title menu's exit button; the program must return 0, close its screen and log the shutdown steps.
# The button only exists while a title park is on screen, so wait until no park load is in progress.
def title_quiet(t):
    lines = t.splitlines()
    last_load = max((i for i, l in enumerate(lines) if "title: load" in l), default=-1)
    last_ready = max((i for i, l in enumerate(lines) if "title: park prepared" in l), default=-1)
    return last_ready > last_load
t = wait_trace(a, title_quiet, limit=180, step=5)
for attempt in range(3):
    a.click_at(619, 447); time.sleep(12)
    try:
        a.read_file("Work:OpenRCT2/rc.txt"); break
    except Exception:
        t = wait_trace(a, title_quiet, limit=120, step=5)
try:
    rc = a.read_file("Work:OpenRCT2/rc.txt").decode("latin-1").strip()
except Exception:
    rc = "no rc.txt (program still running?)"
t = a.read_file("Work:OpenRCT2/trace.txt").decode("latin-1")
screens = [s.get("title", "") for s in a.screens()]
check("clean exit", rc == "rc=0" and "main: context shut down" in t and not any("OpenRCT2" in x for x in screens),
      f"{rc}; screens open: {screens}; shutdown trace {'complete' if 'main: context shut down' in t else 'incomplete'}")

# 2. Audio dump: the mixer output must not be silent ----------------------------------------------
print("[2/4] audio content", flush=True)
a = fresh_game(None, "Work:OpenRCT2/run-ui", {"OPENRCT2_AUDIO_DUMP": "Work:OpenRCT2/audio.raw"})
t = wait_trace(a, lambda t: "audio: dump closed" in t, limit=480, step=10)
try:
    raw = a.read_file("Work:OpenRCT2/audio.raw")
    import struct
    n = min(len(raw) // 2, 400000)
    samples = struct.unpack(">%dh" % n, raw[: n * 2])
    peak = max(abs(s) for s in samples) if samples else 0
    nonzero = sum(1 for s in samples if s != 0)
    check("audio not silent", peak > 500 and nonzero > n // 10, f"{len(raw)} bytes dumped, peak {peak}, {nonzero}/{n} non-zero samples")
except Exception as e:
    check("audio not silent", False, f"no dump: {str(e)[:60]}")
a.exec_command("UnSetEnv OPENRCT2_AUDIO_DUMP", timeout=30)
a.exec_command("Delete >NIL: Work:OpenRCT2/audio.raw", timeout=30)

# 3. Crazy Castle: static and scrolling --------------------------------------------------------------
print("[3/4] Crazy Castle", flush=True)
a = fresh_game(None, "Work:OpenRCT2/run-cc")
t = wait_trace(a, lambda t: t.count("gfx: 100") >= 4, limit=420)
gfx = [l for l in t.splitlines() if "gfx: 100" in l]
f = fps_of(gfx[-1]); check("scenario static fps", f >= 30, f"{f} fps ({gfx[-1][gfx[-1].index('rasterise'):][:40]})")
n0 = t.count("gfx: 100")
a.input_key("down", down=True)
t = wait_trace(a, lambda t: t.count("gfx: 100") >= n0 + 3, limit=120, step=5)
a.input_key("down", down=False)
gfx = [l for l in t.splitlines() if "gfx: 100" in l]
f = fps_of(gfx[-1]); check("scenario scrolling fps", f >= 25, f"{f} fps while scrolling")
kpx = int(re.search(r"for (\d+) kpx", gfx[-1]).group(1))
check("scrolling blits the view", kpx > 15000, f"{kpx} kpx blitted per 100 frames while scrolling (whole-view scrolling)")

# 4. Kahuna Point: crowded park simulation -----------------------------------------------------------
print("[4/4] Kahuna Point (1,560 guests)", flush=True)
a = fresh_game(None, "Work:OpenRCT2/run-kahuna")
t = wait_trace(a, lambda t: "park: import done" in t, limit=600)
time.sleep(15)
a.click_at(17, 13)
t = wait_trace(a, lambda t: t.count("tick: per") >= 3, limit=420)
tl = [l for l in t.splitlines() if "tick: per" in l]
peeps = int(re.search(r"peeps (\d+)", tl[-1]).group(1))
check("crowded park tick cost", peeps < 3500, f"guest updates {peeps} ms per 40 ticks ({peeps / 40:.0f} ms per tick)")

print("\nSUMMARY")
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
print("ALL PASS" if all(ok for _, ok, _ in results) else "SOME CHECKS FAILED")
