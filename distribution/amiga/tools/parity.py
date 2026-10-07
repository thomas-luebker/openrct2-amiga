"""Amiga-side determinism check: run `openrct2-cli simulate` on the emulator and compare the checksums.

The native oracle cannot test changes that only exist behind #ifdef __amigaos__, so these three cases run
the 68k CLI on Amigo instead. Only .park files are usable: an .SC6 seeds the RNG from the clock and gives a
different answer every run.
"""
import os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guest
# Project root that holds build-68k/ next to the fork (the fork is <root>/upstream); override with OPENRCT2_AMIGA_ROOT.
PROJ = os.environ.get("OPENRCT2_AMIGA_ROOT") or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))

CASES = [
    ("Work:OpenRCT2/user/save/cc-old.park", 500, "e6bcc45faa69db5a"),
    ("Work:OpenRCT2/user/save/cc-old.park", 2500, "6b362b8c49539636"),
    ('"Work:OpenRCT2/user/save/Extreme Heights.park"', 500, "58dfbcafc484f9d7"),
]

def push_cli(a, local):
    if local is None:
        print("using the cli already on the guest", flush=True); return
    data = open(local, "rb").read(); CH = 4*1024*1024; parts = []
    for i in range(0, len(data), CH):
        p = f"Work:OpenRCT2/cli.p{i//CH}"; a.write_file(p, data[i:i+CH]); parts.append(p)
    a.exec_command("Delete >NIL: Work:OpenRCT2/openrct2-cli", timeout=60)
    a.exec_command("Join " + " ".join(parts) + " AS Work:OpenRCT2/openrct2-cli", timeout=300)
    for p in parts: a.exec_command(f"Delete >NIL: {p}", timeout=60)
    a.exec_command("Protect Work:OpenRCT2/openrct2-cli +e", timeout=60)
    rc, out = a.exec_command("List Work:OpenRCT2/openrct2-cli LFORMAT %L", timeout=60)
    assert out.strip() == str(len(data)), f"cli size mismatch {out.strip()} vs {len(data)}"
    print(f"cli pushed ({len(data)} bytes)", flush=True)

def run_case(a, park, ticks):
    a.exec_command("Delete >NIL: Work:OpenRCT2/sim.out", timeout=60)
    # `simulate` declares no options of its own and the parser rejects root options before a subcommand,
    # so the paths cannot be given on the command line at all: run from PROGDIR: and let the CLI find
    # PROGDIR:user/config.ini, which already carries them.
    cmd = f"Work:OpenRCT2/openrct2-cli simulate {park} {ticks} >Work:OpenRCT2/sim.out"
    a.exec_command(f"Run >NIL: {cmd}", timeout=60)
    t0 = time.time()
    while time.time() - t0 < 1800:
        time.sleep(20)
        rc, out = a.exec_command("Status", timeout=60)
        if "openrct2-cli" not in out.lower():
            break
    try:
        txt = a.read_file("Work:OpenRCT2/sim.out").decode("latin-1")
    except Exception as e:
        return None, f"no output ({e})"
    # "Completed: <40 hex>" -- the reference figures are the first 16 characters of that digest
    m = re.findall(r"Completed:\s*([0-9a-f]{16,})", txt)
    return (m[-1][:16] if m else None), txt[-400:]

if __name__ == "__main__":
    binary = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PROJ, "build-68k", "openrct2-cli")
    if binary in ("-", "none"):
        binary = None
    # Restart the emulator first: a game left running from an earlier run competes for the CPU and turns
    # a five-minute case into an hour.
    a = guest.restart_amigo()
    push_cli(a, binary)
    bad = 0
    for park, ticks, want in CASES:
        got, tail = run_case(a, park, ticks)
        ok = got == want
        bad += not ok
        name = park.strip('"').split("/")[-1]
        print(f"{name} {ticks}: {got} {'MATCH' if ok else 'MISMATCH, expected ' + want}", flush=True)
        if not ok:
            print("   ", tail.replace("\n", " | ")[-300:], flush=True)
    print("PARITY OK" if bad == 0 else f"PARITY FAILED ({bad})")
    sys.exit(1 if bad else 0)
