# OpenRCT2 on AmigaOS 3.2 (68k) — tester guide

*Build: test25. This is an early, unfinished port. You are testing it — thank you.*

OpenRCT2 is the open-source re-implementation of RollerCoaster Tycoon 2. This build is a
big-endian port of the upstream C++20 engine to 68k AmigaOS, with an Intuition/RTG display
backend instead of SDL. The game logic is bit-exact with the PC version (verified over 5000
simulated ticks); the display and input layer is new.

## 0. Where to get builds

Tester builds are published on GitHub only: https://github.com/thomas-luebker/openrct2-amiga/releases
Each release has the full archive, a small update archive and this guide. Every build is checked on an
emulated 68040 before release: sound (AHI opens and the mixed output is audible), frame rate in a fresh
scenario and while scrolling, and the simulation cost of a park with 1,500 guests.

## 1. What you need

| | Requirement |
|---|---|
| OS | AmigaOS 3.2 (tested on 3.2.3). Other 3.x may work, untested. |
| Graphics | An RTG card with a **Picasso96 or CyberGraphX** driver offering an **8-bit 640×480** mode. AGA/ECS-only machines are not supported. |
| CPU | 68040/68060, **PiStorm** (Emu68) or **Vampire/Apollo**. Tested on an emulated 68040. A 68020/030 runs it, slowly. No FPU needed. |
| RAM | About **320 MB free Fast RAM** for a normal park; a very large park with 1,500 guests reaches ~240 MB and its autosave temporarily needs ~75 MB more, so 512 MB is recommended. If memory is tight, set `autosave = 5` (never) in `user/config.ini`. |
| Disk | ~80 MB for the game, plus your RCT2 data (~150 MB, or ~630 MB with all the ride music). |
| RCT2 data | The **original RollerCoaster Tycoon 2** files (GOG, Steam or CD). Not included, not redistributable. |
| Sound | **AHI** installed, with unit 0 configured (optional: the game is silent without it). |

## 2. Get your RCT2 data onto the Amiga

From your RCT2 installation copy these folders to the Amiga, keeping their names:

```
Data/      ObjData/      Scenarios/      Tracks/
```

Sound effects come from `Data/css1.dat` (5 MB) and the title music from `Data/css17.dat`. The
other `css*.dat` files are the ride music (~480 MB in total): copy the ones you want, or all. Copy over the network, a USB stick, or a CF card.
Example target: `Work:Games/RCT2/`.

## 2b. What to expect at the title screen

The title screen tours two empty RCT2 beginner scenarios (Crazy Castle and Amity Airfield, two minutes
each) instead of the large community parks the PC version shows: those need minutes to load and run at
one or two frames per second on a 68k. Reaching the title screen still takes a while (about half a
minute on a fast machine) because an RCT2 scenario references some 600 objects that all have to be
read from disk. Starting a scenario afterwards is much quicker, since most objects are already loaded.

## 2c. Scrolling

Scrolling with the mouse at the screen edge or with the arrow keys now moves the view by the same
amount per second whatever the frame rate. Earlier builds moved one fixed step per drawn frame, which
crawled at 15 fps and jumped at the map edge.

## 2d. Solid windows

Windows and the two bars are drawn opaque on the Amiga (`solid_windows = true` in `user/config.ini`).
The PC version treats every window as transparent, so the landscape underneath every open window and
both bars was painted again on every scrolled frame; that cost more than half of the scrolling frame
rate. Set `solid_windows = false` if you prefer the transparent look.

## 2e. The other program files

`bin/openrct2` is compiled for a 68020 without FPU and runs everywhere. Two variants sit next to it:

- `bin/openrct2-o2`: the same program compiled for smaller code (-O2 instead of -O3). On real
  68060 and 68080 CPUs with their small caches it may run faster; on a PiStorm or an emulator it
  should make no difference.
- `bin/openrct2-fpu`: compiled for a 68060 with hardware floating point (-m68060 -mhard-float).
  **Needs an FPU**: 68040/68060 with FPU, PiStorm (Emu68), Vampire/Apollo. It will not start on a
  68040LC/68060LC or a plain 68020/030. The game avoids floating point in its hot paths, so the
  gain may be small; we want to know what you measure.

To try one, rename `bin/openrct2` to `bin/openrct2-020` and the variant to `bin/openrct2`, then
compare the fps counter in the same spot of the same park.

## 2f. Big parks and guest path finding

With more than a few hundred guests the simulation itself becomes the limit: guests that cannot
find a route to their goal within the game's junction limit run a search of up to 15,000 tiles on
the PC, and on a 68k two such searches per tick were 80% of the whole simulation. This build limits
those searches to 4,000 tiles (`pathfind_tile_budget` in `user/config.ini`); a search that reaches
its goal is unaffected, only the fallback direction of a failed search can differ. Set it to 15000
for exact PC behaviour, or lower (2000) if a big park still runs in slow motion.

Since test24 a big park stays usable even while the simulation is slow. One simulation tick in a
park with a couple of thousand guests costs far more than a whole frame, and the game used to run
up to four ticks back to back before drawing once, so the picture and the mouse froze for the
length of four ticks: one tester's 2,000-guest park drew about one frame per second. The game now
draws after every tick when a tick is that expensive. The park does not run any faster in game
time, but you can see it and click in it: on the emulator a 2,070-guest park went from 3 to 32
frames per second. Nothing about the simulation changed; every tick is a whole, ordinary tick.

test24 also stopped measuring itself. Every guest was timed with two system-clock reads per tick
whether or not you asked for a trace, which in that park is a quarter of a million clock reads a
second, and a clock read on a PiStorm crosses the bus. The measurement now only runs while a trace
is being written, which on the emulator took a quarter off the cost of a tick.

## 2g. Rain and snow cost a full screen

While weather is drawn, the whole screen is copied to the graphics card every frame. That is
deliberate: the drops are painted over the finished picture and taken away again next frame, so
nothing smaller can be marked as changed, and an earlier build that tried drew rain in only part of
the view. How much it costs depends entirely on how fast your card takes a 640x480 8-bit copy.

Measured on the same park, the same view, nothing else open:

| machine | raining | weather off |
|---|---|---|
| PiStorm (Emu68) | no measurable cost | - |
| Amiga 4000, Zorro RTG card | 9 fps | 34 fps |

On the PiStorm a full-screen copy is a quarter of a millisecond and you will never notice it. On the
Amiga 4000 it is 55 milliseconds, which is three quarters of the frame. If your machine has a
graphics card on Zorro and the game slows down when it rains, put

    render_weather_effects = false

in `user/config.ini`. You lose the rain and snow, and you get the frame rate back. It makes no
difference on a PiStorm, so leave it on there.

## 3. Install the game

1. Extract the archive where there is room, e.g. `Work:Games/`. In a Shell:
   ```
   LhA x OpenRCT2-0.5.5-test7-*-amiga68k.lha Work:Games/
   ```
   You get a drawer `OpenRCT2` with an icon.

   **Updating from an earlier test build:** use the small `...-update.lha` instead. It contains only
   the program, the launcher and the docs. Extract it over your existing `OpenRCT2` drawer; your
   `user/config.ini` and the caches in `user/` stay, so no settings are lost and the slow first
   start is not repeated.
2. Tell the game where your RCT2 data is with an **assign** (this is how the launcher finds it):
   ```
   Assign RCT2: Work:Games/RCT2
   ```
   Put that line into `S:User-Startup` so it survives a reboot.
3. Start it: double-click the **OpenRCT2** icon in the drawer, or in a Shell:
   ```
   CD Work:Games/OpenRCT2
   Execute OpenRCT2
   ```
   (The launcher also accepts the folder as an argument: `Execute OpenRCT2 Work:Games/RCT2/`.)

## 4. First start — be patient

- The first start **builds an index** of all game objects and scenarios into the `user` drawer.
  This takes 1–2 minutes on a 68040 and is much faster on every later start.
- Loading the title screen takes about 30 s on an emulated 68040. test24 reads files the Amiga way
  rather than the way the C library suggested: the directory scan asks AmigaDOS for name, size and
  date in one call per file instead of six, the file buffer is 64 KB instead of 1 KB, and the
  stream no longer asks AmigaDOS where it is before every single read. Reading the 35 MB of object
  data went from 2.0 s to 0.4 s, and the whole start from 40 s to 31 s.
- Then the title sequence plays (parks fly by) and the main menu appears in the middle:
  **New Game**, **Load Game**, **Toolbox**. Top-right: **Options**.
- Expect **~25–30 fps at 640×480** on a fast machine.

## 4b. The frame-rate counter

`show_fps = true` in `user/config.ini` puts the frame rate at the top centre of the screen. On some
machines it showed nothing at all up to test24, on others it worked: a stray write inside the game
clobbers one field of the screen's drawing state, and where those four bytes land depends on how
the heap happens to be laid out on your machine. Where it hit that field, everything drawn straight
to the screen rather than through a window was skipped, the counter included. test25 repairs the
field every frame, so the counter is back where it was missing. Note that deleting `config.ini`
resets `show_fps` to false, so set it again afterwards.

The stray write itself is not found yet. If your trace ever contains the line *"gfx: main render
target origin was clobbered"*, that is the write hitting the screen state on your machine and we
would like to know. Text that turns into nonsense in menus is what the same write would look like
if it lands somewhere else, so tell us about that too.

## 4c. Painting on one core

Painting the view used worker threads by default, which the 68k machines this runs on cannot use:
they have one core, so it only bought context switches. It is off by default since test25
(`multithreading` in `user/config.ini`, also in the options window). On the emulator a
2,070-guest park gained about a frame per second.

## 5. Playing

- **New Game** lists the RollerCoaster Tycoon 1 and 2 scenarios found in your Scenarios folder
  (and Wacky Worlds / Time Twister if you own them), in tabs on the left. Click a scenario to start it; loading takes about a minute.
- Standard OpenRCT2 controls: left-click to select/build, right-drag to scroll the map, mouse
  wheel or the magnifier icons to zoom, `Space`/the top-left icon to pause.
- The disk icon (third toolbar button) has **Save**, **Load**, and **Quit**. Saving works but has
  had little testing — save often and expect surprises.
- The `user/config.ini` file holds settings. `window_width`/`window_height` change the screen
  size; frame rate falls with pixel count (1280×720 runs at ~9 fps on an emulated 68040), so
  640×480 is the recommended default. Set `show_fps = true` to see the frame counter.

## 6. Known limitations of this build

- **Sound and music play through AHI** (`ahi.device` unit 0). Since test20 playback runs in its own process
  ("OpenRCT2 audio") exactly as the AHI autodocs prescribe; builds test16 to test19 could freeze the whole
  machine on PiStorm/Emu68 after a few seconds of sound. If a freeze still happens, start once with
  `SetEnv OPENRCT2_NO_AUDIO 1` to confirm it is the sound path, and send the trace. Install AHI (Aminet `mus/misc/ahiusr_4.18.lha`
  works on 3.2) and configure unit 0 in `Prefs/AHI` — Paula on a plain Amiga, or the Vampire/PiStorm
  driver where one exists. Without AHI the game runs silently. Builds before test16 played only the first two audio buffers (a click and a fraction of a second of music, then silence): the driver queued more requests than ahi.device accepts. test16 double-buffers properly and plays continuously on the emulator; please report whether the title music keeps playing on your machine. Music needs the `css*.dat` files from
  your RCT2 `Data` folder; the optional OpenRCT2 music packs (OGG) are not supported yet.
- **Freeze a few seconds into the title park (PiStorm/Emu68, builds test15 to test22):** test23 keeps the test14
  path finder back and no longer walks the heap every 100 frames unless a trace is written. Bisect switches, each `SetEnv` before starting:
  `OPENRCT2_NO_HEAP_STATS 1`, `OPENRCT2_NO_RLE_FAST 1`, `OPENRCT2_NO_TILE_CULL 1`, `OPENRCT2_SKIP_ENTITIES 1`.
  test24 adds `OPENRCT2_NO_TICKCAP 1`, which puts the frame loop back the way it was before the change described
  in section 2f, in case the new one misbehaves on your machine.
- **RollerCoaster Tycoon 1 scenarios (`.SC4`) play** and their simulation is bit-exact with the
  PC build. Rides that only exist in RCT1 use fallback RCT2 graphics unless you also own RCT1 and
  set `rct1_path` in `user/config.ini` to its folder; the log line *"Park has objects which require
  RCT1 linked"* means exactly that and is not an error.
- Tool cursors (hand, bulldozer, path, ...) are shown through the OS pointer since test18; the text clipboard
  works in text boxes (Ctrl+C/X/V). Both are new and untested on real hardware: if the pointer looks wrong
  or the game misbehaves when a tool is selected, say so.
- test17 and test18 returned large freed memory blocks to the system at once; one tester saw garbled text
  with that. Since test19 that path is off by default. Testers who want to help find the cause can switch it
  on with `SetEnv OPENRCT2_BIGALLOC 1` in the Shell before starting and report whether text breaks.
- Multiplayer, plugins and the scenario editor are untested.
- The park load is CPU-bound (object loading, tile import); a real 68060 or PiStorm will be
  faster than the emulated 68040 the numbers above come from.

## 7. If it is slow: send us a performance trace

If the frame rate is low, please run it once with the trace on and send us the file, it tells us where
the time goes (and, if the game hangs during loading, where it stopped):

```
SetEnv OPENRCT2_TRACE T:openrct2-trace.txt
Execute OpenRCT2
```

Let the title screen run for a minute, quit, and send `T:openrct2-trace.txt` together with your
hardware (CPU/accelerator, graphics card and driver, screen mode). The lines that matter look like
`gfx: 100 frames in 4123 ms = 24.25 fps; rasterise 2100 ms, blit 900 ms for 30000 kpx (chunky)` and
`frame: per 20 draws: events 40 ms, sleep 0 ms (0 times), ticks 800 ms (80 ticks), input+windows 20 ms, draw 700 ms`
(where the frame time goes: simulation ticks, drawing, input), plus `tick: per 40 ticks: ...` with the
cost of each simulation subsystem. The title screen park is the heaviest thing in the game; please also
report the frame rate inside a freshly started scenario, that is what matters for playing.
If the game hangs while loading (one PiStorm tester saw it stop at "Loading title sequence (30%)" and
the machine's disk access died with it), please try once with sound disabled to isolate the audio path:
`SetEnv OPENRCT2_NO_AUDIO 1` before starting. If that loads, the hang is in the audio code; send the
trace of the hanging run either way.

An experimental direct framebuffer write can be tried with `SetEnv OPENRCT2_BLIT direct` before starting
(it hung one PiStorm during loading, so it is off by default; tell us what it does on your card). A smaller
screen mode (`window_width`/`window_height` in `user/config.ini`) scales the cost down almost linearly.

## 8. Reporting problems

Send: your machine (CPU, RAM, graphics card and driver, OS version), what you did, what you
expected, what happened, and a screenshot if you can.

For crashes or hangs, switch on the trace log **before** starting the game:

```
SetEnv OPENRCT2_TRACE T:openrct2-trace.txt
```

Reproduce the problem, then send `T:openrct2-trace.txt`. Switch it off again afterwards
(it slows loading down noticeably):

```
UnSetEnv OPENRCT2_TRACE
```

## 9. Uninstall

Delete the `OpenRCT2` drawer and remove the `Assign RCT2:` line from `S:User-Startup`.
Nothing is written outside the drawer.

---
OpenRCT2 is GPLv3. This port lives on the `amiga` branch of the project repository.
