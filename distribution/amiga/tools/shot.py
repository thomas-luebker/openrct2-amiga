"""Save a screenshot of the Amigo guest as PNG: python3 shot.py out.png [screenindex]"""
import os, sys, struct, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guest import guest

def png(path, w, h, rgb_rows):
    raw = b"".join(b"\x00" + r for r in rgb_rows)
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))

def shot_to_png(a, path, screen=0):
    s = a.screenshot(screen=screen)
    rows = []
    if s.palette is not None:
        pal = [bytes(c) for c in s.palette]
        for y in range(s.height):
            line = s.pixels[y * s.width:(y + 1) * s.width]
            rows.append(b"".join(pal[p] if p < len(pal) else b"\0\0\0" for p in line))
    else:
        for y in range(s.height):
            rows.append(s.pixels[y * s.width * 3:(y + 1) * s.width * 3])
    png(path, s.width, s.height, rows)
    return s.width, s.height, (len(s.palette) if s.palette else 0)

if __name__ == "__main__":
    a = guest()
    print(a.screens())
    print(shot_to_png(a, sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0))
