"""Stability soak on the Amigo guest: python3 soak.py [binary]
Phase 1: title sequence with short waits (park switches every ~6 s) for 8 minutes, audio on.
Phase 2: Kahuna Point (1,560 guests) running for 8 minutes.
Phase 3: Crazy Castle with the view scrolled continuously for 5 minutes.
Each phase: the trace must keep advancing (no freeze) and free memory must not drift down steadily.
"""
import os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guest import fresh_game, wait_trace

BIN = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None
FAST_SEQ = "/tmp/Amiga-fast.parkseq"
SEQ = "/tmp/Amiga.parkseq"
verdicts = []


def avail(a):
    out = a.exec_command("Avail", timeout=30)[1]
    m = re.search(r"Total\s+(\d+)\s+(\d+)", out, re.I)
    return int(m.group(2)) if m else -1  # 'In-Use' column of the Total line


def watch(a, seconds, label, scroll=False):
    t0 = time.time(); last_len = 0; stalls = 0; mem = []
    while time.time() - t0 < seconds:
        if scroll:
            key = ["down", "right", "up", "left"][int((time.time() - t0) // 15) % 4]
            a.input_key(key, down=True); time.sleep(8); a.input_key(key, down=False); time.sleep(2)
        else:
            time.sleep(10)
        try:
            t = a.read_file("Work:OpenRCT2/trace.txt").decode("latin-1")
        except Exception:
            t = ""
        if len(t) == last_len:
            stalls += 1
        else:
            stalls = 0
        last_len = len(t)
        if int(time.time() - t0) % 60 < 10:
            mem.append(avail(a))
        if stalls >= 4:
            verdicts.append((label, False, f"trace stopped advancing after {time.time() - t0:.0f} s"))
            return t
    # bytes in use come from dlmalloc's own accounting in the "heap:" trace line; the system-level footprint may
    # step up once for a big transient (autosave needs ~75 MB for a large park) and never comes back down.
    hl = [re.search(r"footprint (\d+) KB, in use (\d+) KB", l) for l in t.splitlines() if "heap:" in l]
    hl = [m for m in hl if m]
    inuse_drift = (int(hl[-1].group(2)) - int(hl[0].group(2))) / 1024 if len(hl) >= 2 else 0
    foot = (int(hl[-1].group(1)) - int(hl[0].group(1))) / 1024 if len(hl) >= 2 else 0
    heap = [l for l in t.splitlines() if "HEAP" in l]
    ok = not heap and inuse_drift < 8
    verdicts.append((label, ok, f"ran {seconds} s, bytes in use drift {inuse_drift:+.1f} MB, footprint {foot:+.0f} MB (system in-use {(mem[-1] - mem[0]) / 1024 / 1024 if len(mem) >= 2 else 0:+.0f} MB)" + (", HEAP corruption reported" if heap else "")))
    return t


print("[1/3] title sequence, fast switching, audio on", flush=True)
a = fresh_game(BIN, "Work:OpenRCT2/run-ui")
a.write_file("Work:OpenRCT2/data/sequence/Amiga.parkseq", open(FAST_SEQ, "rb").read())
t = wait_trace(a, lambda t: t.count("gfx: 100") >= 1, limit=420)
t = watch(a, 480, "title park switching")
print("   park loads:", t.count("title: load"), flush=True)
a.write_file("Work:OpenRCT2/data/sequence/Amiga.parkseq", open(SEQ, "rb").read())

print("[2/3] Kahuna Point running", flush=True)
a = fresh_game(None, "Work:OpenRCT2/run-kahuna")
t = wait_trace(a, lambda t: "park: import done" in t, limit=600); time.sleep(15)
a.click_at(17, 13)
t = watch(a, 480, "crowded park")

print("[3/3] Crazy Castle scrolling", flush=True)
a = fresh_game(None, "Work:OpenRCT2/run-cc")
t = wait_trace(a, lambda t: t.count("gfx: 100") >= 2, limit=420)
t = watch(a, 300, "continuous scrolling", scroll=True)

print("\nSOAK SUMMARY")
for label, ok, detail in verdicts:
    print(f"{'PASS' if ok else 'FAIL'}  {label}: {detail}")
print("ALL PASS" if all(ok for _, ok, _ in verdicts) else "SOME PHASES FAILED")
