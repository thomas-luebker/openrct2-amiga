import os, sys, time, subprocess, signal
sys.path.insert(0, os.environ.get("AMIGA_FLEET_SCRIPTS") or os.path.expanduser("~/Development/AllAmigaTooling/skills/amiga-fleet/scripts"))
from fleet import connect
def guest():
    return connect("Amigo", timeout=20, ignore_claim=True)
def free(a):
    try: a.exec_command("Echo ok", timeout=10); return True
    except Exception: return False
def restart_amigo():
    out = subprocess.run(["pgrep", "-f", "Wrapper/Amigo.app/Amigo"], capture_output=True, text=True).stdout.split()
    for pid in out: os.kill(int(pid), signal.SIGKILL)
    time.sleep(3); subprocess.run(["open", "-a", "Amigo"])
    for i in range(60):
        time.sleep(5)
        try:
            a = guest(); a.ping()
            if free(a): print(f"  (Amigo restarted, agent up after ~{(i+1)*5} s)", flush=True); return a
        except Exception: pass
    raise SystemExit("Amigo did not come back")
def ensure_free():
    try:
        a = guest()
        if free(a):
            return a
        print("guest busy: BREAK", flush=True); a.break_command(); time.sleep(6)
        if free(a):
            return a
    except Exception as e:
        print("guest unreachable:", str(e)[:60], flush=True)
    return restart_amigo()

def fresh_game(binary=None, run_script="Work:OpenRCT2/run-ui", extra_env=None):
    """Restart the emulator, verify nothing of the game is left, push a binary if given, launch the run script."""
    a = restart_amigo()
    rc, out = a.exec_command("Status", timeout=30)
    if "openrct2" in out.lower():
        raise SystemExit("game still running after restart:\n" + out)
    if binary is not None:
        data = open(binary, "rb").read()
        CH = 4 * 1024 * 1024; parts = []
        for i in range(0, len(data), CH):
            a.write_file(f"Work:OpenRCT2/openrct2.{i//CH}", data[i:i+CH]); parts.append(f"Work:OpenRCT2/openrct2.{i//CH}")
        a.exec_command("Delete >NIL: Work:OpenRCT2/openrct2", timeout=30)
        a.exec_command("Join " + " ".join(parts) + " AS Work:OpenRCT2/openrct2", timeout=120)
        for p in parts: a.exec_command(f"Delete >NIL: {p}", timeout=30)
        rc, out = a.exec_command("List Work:OpenRCT2/openrct2 LFORMAT %L", timeout=30)
        if out.strip() != str(len(data)):
            raise SystemExit(f"binary size mismatch on guest: {out.strip()!r} vs {len(data)}")
    a.exec_command("Delete >NIL: Work:OpenRCT2/trace.txt", timeout=30)
    rc, out = a.exec_command("List Work:OpenRCT2/trace.txt", timeout=30)
    if "object not found" not in out and rc == 0:
        raise SystemExit("trace.txt could not be deleted:\n" + out)
    a.exec_command("SetEnv OPENRCT2_TRACE Work:OpenRCT2/trace.txt", timeout=30)
    for k, v in (extra_env or {}).items():
        a.exec_command(f"SetEnv {k} {v}", timeout=30)
    a.exec_command(f"Run >NIL: Execute {run_script}", timeout=30)
    # Park the pointer mid-screen before the game opens its screen: left at the screen edge (where the emulator
    # restart leaves it) it edge-scrolls the view off the map for the whole start-up, by a run-dependent amount.
    try: a.input_script([("move", 320, 240), ("wait", 2)])
    except Exception: pass
    return a

def wait_trace(a, predicate, limit=400, step=10):
    """Poll the trace until predicate(text) is true or the time limit passes; returns the text."""
    import time as _t
    t0 = _t.time(); t = ""
    while _t.time() - t0 < limit:
        _t.sleep(step)
        try: t = a.read_file("Work:OpenRCT2/trace.txt").decode("latin-1")
        except Exception: continue
        if predicate(t): break
    return t
