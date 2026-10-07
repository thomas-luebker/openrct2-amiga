"""Does the program give its memory back to the system when it exits?

AmigaOS does not reclaim a program's AllocMem when it exits: whatever the allocator has not freed is
lost until the next reboot. Nothing else in the gate catches this -- parity, the release check and the
soak all measure a single run while it is still alive -- and it cost 132 MB on the A4000 the first time
the exec-backed large-block path was made the default (2026-09-17).

  python3 leak_check.py [machine] [--push]
"""
import os, re, sys, time
sys.path.insert(0, os.environ.get("AMIGA_FLEET_SCRIPTS") or os.path.expanduser("~/Development/AllAmigaTooling/skills/amiga-fleet/scripts"))
from fleet import connect
# Project root that holds build-68k/ next to the fork (the fork is <root>/upstream); override with OPENRCT2_AMIGA_ROOT.
PROJ = os.environ.get("OPENRCT2_AMIGA_ROOT") or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))

PATHS = {
    "Amigo":   ("Work:OpenRCT2", "Work:OpenRCT2/user/save/cc-old.park"),
    "PiStorm": ("Work:Games/OpenRCT2", "Work:Games/OpenRCT2/user/save/Heide-Park.park"),
    "A4000":   ("Games:OpenRCT2Test/OpenRCT2", "Games:OpenRCT2Test/OpenRCT2/user/save/cc-old.park"),
}
# The CLI lives next to the game on Amigo and the A4000, and in the game directory on the PiStorm.
CLI = {"Amigo": "Work:OpenRCT2/openrct2-cli", "PiStorm": "Work:Games/OpenRCT2/openrct2-cli",
       "A4000": "Games:OpenRCT2Test/OpenRCT2/openrct2-cli"}
TOLERANCE_MB = 2.0

def fast_in_use(a):
    rc, out = a.exec_command("Avail", timeout=60)
    m = re.search(r"fast\s+(\d+)\s+(\d+)", out)
    return int(m.group(2)) if m else -1

def push(a, local, remote):
    data = open(local, "rb").read(); CH = 4*1024*1024; parts = []
    for i in range(0, len(data), CH):
        q = f"{remote}.p{i//CH}"; a.write_file(q, data[i:i+CH]); parts.append(q)
    a.exec_command(f"Delete >NIL: {remote}", timeout=180)
    a.exec_command("Join " + " ".join(parts) + f" AS {remote}", timeout=900)
    for q in parts: a.exec_command(f"Delete >NIL: {q}", timeout=120)
    a.exec_command(f"Protect {remote} +e", timeout=90)
    rc, out = a.exec_command(f"List {remote} LFORMAT %L", timeout=90)
    assert out.strip() == str(len(data)), f"size mismatch {out.strip()} vs {len(data)}"
    print("cli pushed", flush=True)

def one(a, home, park, ticks, env):
    for k in ("OPENRCT2_NO_BIGALLOC",):
        a.exec_command(f"UnSetEnv {k}", timeout=30)
    for k, v in env.items():
        a.exec_command(f"SetEnv {k} {v}", timeout=30)
    cli = CLI[MACHINE]
    a.write_file(f"{home}/leak-run", f'cd {home}\n{cli} simulate "{park}" {ticks} >{home}/leak.out\n'.encode())
    a.exec_command(f"Run >NIL: Execute {home}/leak-run", timeout=90)
    t0 = time.time()
    while time.time() - t0 < 2400:
        time.sleep(10)
        rc, out = a.exec_command("Status", timeout=60)
        if "openrct2-cli" not in out.lower():
            return
    raise SystemExit("the CLI did not finish")

if __name__ == "__main__":
    MACHINE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "Amigo"
    home, park = PATHS[MACHINE]
    a = connect(MACHINE, timeout=30, ignore_claim=True)
    rc, out = a.exec_command("Status", timeout=90)
    assert "openrct2" not in out.lower(), "something of the game is still running"
    if "--push" in sys.argv:
        push(a, os.path.join(PROJ, "build-68k", "openrct2-cli"), CLI[MACHINE])
    bad = 0
    for label, env in (("exec-backed", {}), ("kept in heap", {"OPENRCT2_NO_BIGALLOC": "1"})):
        before = fast_in_use(a)
        one(a, home, park, 200, env)
        time.sleep(5)
        leaked = (fast_in_use(a) - before) / 1048576.0
        ok = leaked <= TOLERANCE_MB
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {label}: {leaked:+.1f} MB left behind after exit", flush=True)
    print("LEAK CHECK OK" if bad == 0 else f"LEAK CHECK FAILED ({bad})")
    sys.exit(1 if bad else 0)
