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

| | Amiga 4000, 68060 at 50 MHz, Zorro RTG | Amiga 1200 + PiStorm (Emu68) |
|---|---|---|
| normal park | 33–35 fps (the frame cap) | frame cap |
| large park, quiet view | — | 23–25 fps |
| large park, built-up view | 0.14 fps | ~8 fps |
| while it rains | 9 fps | no measurable cost |
| loading a scenario | ~4½ minutes | ~40 s |

What the numbers mean if you are wondering whether your machine will do:

- **A normal park plays at the frame cap on both.** That is what most people play.
- **A park with two thousand guests is a PiStorm job.** On a 68060 it is not playable.
- **Rain costs a whole-screen copy every frame.** That is free on a PiStorm and three quarters of the
  frame on a Zorro graphics card: set `render_weather_effects = false` in `user/config.ini` there.
- **Where the time goes in a big park**: about 40 ms per simulation tick (three quarters of it the
  guests) and, in a built-up view, about 90 ms building the paint list. The copy to the graphics card
  is a quarter of a millisecond on a PiStorm and 55 ms over Zorro.
- **A hardware-FPU build buys nothing.** On a real 68060 with a 68882 it loaded 622 objects in 116 s
  against 118 s for the soft-float build. The game keeps floating point out of its hot paths.

## Requirements

- AmigaOS 3.2 (tested on 3.2.3); an RTG card with a Picasso96 or CyberGraphX driver and an 8-bit
  640×480 mode (AGA/ECS-only machines are not supported).
- 68040/68060, PiStorm (Emu68) or Vampire/Apollo. A 68020/030 runs it, slowly.
- **Memory**: a normal park uses about 165 MB and the allocator holds roughly 220 MB from the system;
  a park with 2,000 guests reaches about 240 MB and its autosave briefly wants ~75 MB more. 512 MB of
  Fast RAM is the comfortable figure, 320 MB works for ordinary parks. Set `autosave = 5` (never) in
  `user/config.ini` if memory is tight.
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
