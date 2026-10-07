"""Partial-repaint consistency check: python3 repaint_check.py <tag> [binary] [ENV=1 ...]
Loads Kahuna Point (paused), scrolls onto the busy area, screenshots the view (S1), opens and closes the map window
with Tab so the area underneath is repainted in dirty blocks, screenshots again (S2). S1 and S2 must be identical:
any cull or sort-order glitch in the block repaint shows up as differing pixels. Saves both PNGs under the tag, in $REPAINT_OUT (default: the current directory).
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guest import fresh_game, wait_trace
from shot import shot_to_png
tag = sys.argv[1]
binary = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
env = dict(kv.split("=", 1) for kv in sys.argv[3:])
out = os.environ.get("REPAINT_OUT", ".")  # where the two PNGs go
a = fresh_game(binary, "Work:OpenRCT2/run-kahuna", env)
t = wait_trace(a, lambda t: "park: import done" in t, limit=600); time.sleep(15)
for key, secs in ((("down", 1.5), ("right", 1.5)) if "static" not in tag else ()):
    a.input_key(key, down=True); time.sleep(secs); a.input_key(key, down=False); time.sleep(3)
time.sleep(8)
def grab(name):
    s = a.screenshot(screen=0)
    shot_to_png(a, f"{out}/{tag}-{name}.png")
    return bytes(s.pixels), s.width, s.height
s1, w, h = grab("s1")
a.input_key("tab"); time.sleep(4)
sw, _, _ = grab("win")
a.input_key("backspace"); time.sleep(6)
s2, _, _ = grab("s2")
diff = sum(1 for i in range(len(s1)) if s1[i] != s2[i])
covered = sum(1 for i in range(len(s1)) if s1[i] != sw[i])
print(f"{tag}: {w}x{h}, window covered {covered} px, S1 vs S2 differ in {diff} px")
for k in env: a.exec_command(f"UnSetEnv {k}", timeout=30)
