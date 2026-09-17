<p align="center"><img src="distribution/amiga/screenshots/title.png" width="640" alt="OpenRCT2 title screen on AmigaOS, 640x480, 8-bit RTG"></p>

<h1 align="center">OpenRCT2 for AmigaOS (68k)</h1>

<p align="center">RollerCoaster Tycoon 2, running natively on a big-endian 68k Amiga.<br>
A port of <a href="https://github.com/OpenRCT2/OpenRCT2">OpenRCT2</a> to AmigaOS 3.x — Picasso96/CyberGraphX display, Intuition input, AHI sound.</p>

<p align="center"><a href="https://github.com/thomas-luebker/openrct2-amiga/releases"><b>Download the tester build</b></a> · <a href="distribution/amiga/TESTER-GUIDE.md">Tester guide</a> · <a href="distribution/amiga/BUILDING.md">Building</a> · <a href="AMIGA_PORT.md">How the port works</a></p>

---

## What this is

OpenRCT2 is the open-source re-implementation of RollerCoaster Tycoon 2. This repository carries the
`amiga` branch: the same engine cross-compiled for m68k AmigaOS 3.x with bebbo's GCC 16, no SDL, no
threads, soft float, big-endian. It is a fork; upstream declined to merge it, so it lives here.

| | |
|---|---|
| ![RCT1 Forest Frontiers](distribution/amiga/screenshots/rct1-forest-frontiers.png) | ![RCT2 Electric Fields](distribution/amiga/screenshots/rct2-electric-fields.png) |
| RCT1 *Forest Frontiers* | RCT2 *Electric Fields* |

## Status

- **Plays.** RCT2 scenarios (`.sc6`, incl. Wacky Worlds / Time Twister) and RCT1 scenarios (`.sc4`,
  incl. Added Attractions / Loopy Landscapes) load natively and play; `.park` saves load.
- **Bit-exact.** The simulation produces the same entity checksums as the x86-64/arm64 build over
  5000 ticks, and scenario loads are identical at tick 0 — verified on a 68040 against a native build
  of the same tree.
- **Display and input** on an 8-bit RTG screen (640×480 recommended), mouse and keyboard through
  Intuition.
- **Sound and music** through `ahi.device`: the RCT2 sound bank and `css*.dat` music. OpenRCT2's own
  Ogg music packs are not supported (no Vorbis decoder in this build).
- Not yet: networking, scripting. Mouse cursor shapes and the text clipboard work; the hardware-FPU
  build runs but is no faster (see below).

## Performance

Measured on real hardware, not estimated. A "normal park" is a freshly started scenario; the large
park is a community one with 2,000 guests.

Each park is loaded and the camera is never moved, so all three machines draw the same picture from the
park's own saved viewpoint; the simulation is checked to be running before a frame is counted. The frame
cap is 40.

| | emulator (OS 3.2.3) | A1200 + PiStorm (Emu68) | A4000, 68060 @ 100 MHz |
|---|---|---|---|
| Crazy Castle, 3 guests | 35–38 fps | 39–40 fps | 36–37 fps |
| Extreme Heights, 172 guests | 34–39 fps | 38–40 fps | 32–35 fps |
| Heide Park, 2,085 guests | 15–16 fps | 16–18 fps | 2–3 fps |
| loading any of them | 26–32 s | 27 s | 161–205 s |

The simulation on its own, measured headless with `openrct2-cli simulate` so no drawing is included, and
with matching checksums across all three machines:

| ms per tick | emulator | PiStorm | A4000 @ 100 MHz |
|---|---|---|---|
| Crazy Castle, 3 guests | 0.42 | 0.40 | 2.52 |
| Extreme Heights, 172 guests | 2.33 | 1.67 | 17.82 |
| Heide Park, 2,085 guests | 54.06 | 28.07 | 281.07 |
| cost per guest per tick | 25.8 µs | 13.3 µs | 134 µs |

A tick has to finish in 25 ms for the game to keep real time, which puts the PiStorm at roughly 1,800
guests, the emulator at 950 and a 100 MHz 68060 at 180. **Emu68 recompiles 68k code to ARM rather than
executing it, and is about ten times faster per guest than a real 68060 at twice its stock clock** —
that gap, not the 68k clock, is what the columns are really comparing.

> Measuring this is easy to get wrong. The wall clock of one `simulate` run is mostly loading objects,
> so timing a single run measures the loader; the figures above are the slope between two tick counts.
> A machine's first run on a park also builds the object and scenario indexes and reads 30–60 % high.
> And a paused game draws at the frame cap while simulating nothing. All three produced confident,
> wrong answers before the harness in `spike/mini/` was made to rule them out.

### How many guests will my machine take?

This is the question that decides whether a park stays playable, and it has a straight answer,
because the simulation cost is almost entirely the guests and it scales with how many there are.
A tick has to fit in about 50 ms to feel alive:

| machine | cost per guest per tick | keeps real time up to |
|---|---|---|
| 68060 at 100 MHz | 134 µs | **~180 guests** |
| emulator (OS 3.2.3) | 25.8 µs | **~950 guests** |
| PiStorm (Emu68) | 13.3 µs | **~1,800 guests**, though drawing then becomes the limit |

Past that point the game does not stutter, it runs in **slow motion**: the port caps the ticks it will
attempt per frame, so the picture stays smooth while the park's clock falls behind. A healthy frame rate
on a crowded park is therefore not on its own proof that the machine is keeping up.

Other things worth knowing:

- **A normal park plays at the frame cap on every machine here**, which is what most people play.
  Doubling a 68060's clock does not change that, because the frame loop rather than the processor is
  the limit there.
- **Doubling the clock doubles everything processor-bound** almost exactly: tick 2.07×, guest updates
  2.1×. The copy to a Zorro graphics card improves only 1.5×, because the bus does not get faster.
- **Rain costs a whole-screen copy every frame.** Free on a PiStorm, three quarters of the frame on a
  Zorro card: set `render_weather_effects = false` in `user/config.ini` there.
- **Where the time goes in a big park.** On a PiStorm with 2,070 guests, per frame in a built-up view:
  about 35 ms of simulation and 15 ms of drawing. The tick is almost entirely the guests, the guests are
  almost entirely walking, and **walking is about 80 % path finding** — 31 searches a tick, 229 tiles
  examined per search. Inside the drawing, building the paint list is two thirds of it; the ground is
  the largest single item there and the sprites the rest. The copy to the card is a quarter of a
  millisecond on a PiStorm and 55 ms over Zorro.
- **The simulation can be measured exactly.** `openrct2-cli simulate <park> <ticks>` runs a fixed park
  for a fixed number of ticks with no drawing and prints a checksum, so a change can be timed the same
  way twice. Two traps: the answer from a machine's *first* run on a park includes building the object
  and scenario indexes and can be 60 % high, and `simulate` takes no command-line options, so the RCT2
  path has to come from `user/OpenRCT2/config.ini`.
- **Profiling on this hardware has to calibrate itself.** One system-clock read pair costs 20 µs on a
  PiStorm, which is more than most of the things a probe measures, so the port measures that cost at
  startup and subtracts it. Figures taken before that was done overstated everything.
- **A hardware-FPU build buys nothing.** On a real 68060 with a 68882 it loaded 622 objects in 116 s
  against 118 s for the soft-float build. The game keeps floating point out of its hot paths.

## Requirements

- AmigaOS 3.2 (tested on 3.2.3); an RTG card with a Picasso96 or CyberGraphX driver and an 8-bit
  640×480 mode (AGA/ECS-only machines are not supported).
- 68040/68060, PiStorm (Emu68) or Vampire/Apollo. A 68020/030 runs it, slowly.
- **Memory**: about **105 MB for a normal park** and **94 MB for Heide Park with 2,000 guests** —
  both measured as memory held from the system, which is now within a megabyte of what the game is
  actually using. A big park is not the expensive case; the object graphics a park pulls in are.
  **128 MB of Fast RAM is enough**, which is the ceiling on most classic accelerators; autosave
  briefly wants more, so set `autosave = 5` (never) in `user/config.ini` if memory is tight.
- **Disk**: about 80 MB for the game, plus your RCT2 data (~150 MB, or ~630 MB with all the music).
- AHI for sound (optional; silent without it).
- The data files of the original RollerCoaster Tycoon 2 (GOG, Steam or CD). Not included.

See the [tester guide](distribution/amiga/TESTER-GUIDE.md) for installation.

## Building

Cross-compile on Linux or macOS: [distribution/amiga/BUILDING.md](distribution/amiga/BUILDING.md)
covers the compiler, the four cross-built dependencies (`build-deps.sh`), `configure.sh` and packaging.

## Credits and licence

OpenRCT2 is © the OpenRCT2 developers, GPLv3 — see [README.upstream.md](README.upstream.md),
[contributors.md](contributors.md) and [licence.txt](licence.txt). RollerCoaster Tycoon 2 is © Chris Sawyer
and Atari; you need your own copy. The AmigaOS port is by Thomas Lübker, developed with Claude Code;
it is licensed under the same GPLv3.
