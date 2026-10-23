*This project has been created as part of the 42 curriculum by naarai.*

# Fly-in

## Description

Fly-in is a drone-fleet routing simulation written in Python. A map file
describes a network of zones (nodes) joined by bidirectional connections
(edges). Every drone starts in the start zone, and the goal is to move all of
them to the end zone **in as few simulation turns as possible**, while
respecting the movement rules of the subject:

- a zone holds at most `max_drones` drones (1 by default); the start and end
  zones have no limit;
- a connection lets at most `max_link_capacity` drones (1 by default) cross
  it in the same turn;
- entering a `normal` or `priority` zone takes 1 turn, entering a
  `restricted` zone takes 2 turns (the drone spends one turn on the
  connection and must land on the next one), and a `blocked` zone can never
  be entered;
- `priority` zones are preferred when several routes are equally short.

The program parses and validates the map, computes distances to the goal,
schedules the moves of every drone turn by turn, checks every turn against
the rules, prints the turn log in the required format, and shows the run in
the terminal and/or in a graphical window (pygame-ce). No graph library is
used: the graph, the shortest-path search and the scheduler are written by
hand, as the subject requires. The code is object-oriented, type-annotated,
and passes `flake8` and `mypy --strict`.

### Input format

A map is a UTF-8 text file:

```text
nb_drones: 5

start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
connection: hub-roof1
connection: corridorA-tunnelB [max_link_capacity=2]
```

| Line | Meaning |
| --- | --- |
| `nb_drones: <n>` | Number of drones, a positive integer. **Must be the physical first line of the file.** |
| `start_hub: <name> <x> <y> [metadata]` | The start zone (exactly one). |
| `end_hub: <name> <x> <y> [metadata]` | The end zone (exactly one). |
| `hub: <name> <x> <y> [metadata]` | A regular zone. |
| `connection: <name1>-<name2> [metadata]` | A bidirectional connection between two zones declared earlier. |
| `# ...` | A comment line (only whole lines; a `#` after a declaration is an error). Blank lines are ignored too. |

Zone metadata (optional, any order): `zone=normal|blocked|restricted|priority`
(default `normal`), `color=<word>` (default none), `max_drones=<n>` (default 1).
Connection metadata: `max_link_capacity=<n>` (default 1).

The parser stops at the first problem and reports the line and the cause.
It rejects, among others: a first line that is not `nb_drones:`, a
non-positive drone count or capacity, a non-integer coordinate, an unknown
zone type, an unknown or repeated metadata key, a malformed `[...]` block, a
zone name containing `-`, a duplicate zone name, a second `start_hub` or
`end_hub`, a connection to a zone not declared yet, a duplicate connection
(`a-b` and `b-a` are the same), and a missing `start_hub` or `end_hub`.
`zone=blocked` is not allowed on the start or end zone. As the subject says,
`max_drones` on the start and end zones is accepted and ignored. A map whose
end zone cannot be reached from the start zone is reported after parsing.

### Output format

Standard output holds **only** the turn log: one line per turn, listing the
moves of that turn separated by spaces, in drone number order.

- `D<ID>-<zone>`: drone `<ID>` entered `<zone>` this turn (including a drone
  landing in a restricted zone after its turn on the connection).
- `D<ID>-<connection>`: drone `<ID>` took off toward a restricted zone and is
  on the connection this turn. The connection is named as it was declared in
  the map (`zone_a-zone_b`).
- Drones that do not move are left out; a delivered drone no longer appears.
  The run ends when every drone is in the end zone.

Everything else goes to standard error: the terminal view, warnings, errors,
and a final summary line with the total number of turns and two of the
subject's secondary metrics (average delivery turn per drone, average moves
per turn):

```text
summary: 5 turns, 5 drones, 4.20 turns per drone on average, 3.40 moves per turn
```

So `python3 fly_in.py map.txt 2>/dev/null` prints exactly the required output.

## Instructions

### Requirements

- Python 3.10 or later (the subject's requirement; the checks below were run
  with Python 3.14).
- `pygame-ce` (>= 2.5) for the graphical view only. It is a drop-in fork of
  pygame, imported as `pygame`. Without it, the program still runs with
  `--visual terminal` or `--visual none`.
- `flake8` and `mypy` for `make lint` / `make lint-strict`.
- `pytest` for `make test` (the unit tests in `tests/`).

All of them are listed in `requirements.txt`. The Makefile is written for Linux
(it uses `.venv/bin/python`).

The maps handed out with the subject (`maps.tar.gz`) are not part of this
repository; download the archive from the subject page and extract it, e.g.
with `tar -xzf maps.tar.gz`. Only `maps/subject_example.txt` (the example of
the subject) is included.

### Makefile

| Rule | What it does |
| --- | --- |
| `make install` | Creates `.venv` (if it is absent or has no working pip) and installs `requirements.txt` into it. |
| `make run` | Runs `maps/subject_example.txt`. Override the map with `MAP=` and add options with `ARGS=`, e.g. `make run MAP=path/to/map.txt ARGS="--visual both"`. |
| `make debug` | The same run under `pdb`, with `FLYIN_DEBUG=1` so that unexpected exceptions reach the debugger instead of being turned into a one-line error. |
| `make lint` | `flake8 .` and `mypy .` with the flags the subject requires (`--warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs`). |
| `make lint-strict` | `flake8 .` and `mypy . --strict`. |
| `make test` | Runs the unit tests in `tests/` (`pytest tests -q`). |
| `make clean` | Removes `__pycache__`, `.mypy_cache`, `.pytest_cache` and `*.pyc` / `*.pyo` files (outside `.venv`). |
| `make fclean` | `clean`, then removes `.venv`. |

`run`, `debug`, `lint`, `lint-strict` and `test` run `make install` first when
`.venv` has not been installed yet or `requirements.txt` changed.

### Running directly

```sh
make install
.venv/bin/python fly_in.py MAP [options]
```

| Option | Effect |
| --- | --- |
| `--visual {terminal,graphical,both,none}` | How to show the run (default `terminal`). `none` prints only the turn log and the summary. |
| `--delay SECONDS` | Seconds each turn stays on screen in the graphical view, from 0 to 60 (default 0.5). |
| `--step` | Advance one turn at a time: Enter in the terminal view, the right arrow in the graphical view. With `both`, the window drives the steps. In the terminal view, step mode is only used when standard input is a terminal, so piped runs never block. |
| `--parse-only FILE` | Parse `MAP`, write the parsed world to `FILE` as JSON, and stop without simulating. |
| `--from-world` | Read `MAP` as a world JSON file written by `--parse-only` instead of a map file, and simulate it. |
| `--save-run FILE` | Write every turn's moves and the state after it to `FILE` as JSON. Cannot be combined with `--parse-only`. |
| `-h`, `--help` | Show the help and exit. |

**Maps that start with comments.** The parser reads the physical first line
as the `nb_drones:` header (the subject: "The first line must define the
number of drones"), so a file whose first line is a comment or a blank line is
rejected:

```text
$ .venv/bin/python fly_in.py comment_first.txt
error: line 1: the first line must be 'nb_drones: <n>'
```

The maps distributed with the subject begin with comment lines. To run one,
drop everything before its `nb_drones:` line into a temporary file and run
that file:

```sh
sed -n '/^nb_drones:/,$p' path/to/map.txt > /tmp/map.txt
make run MAP=/tmp/map.txt
```

### Exit codes

| Code | When |
| --- | --- |
| `0` | The run finished (or `--parse-only` wrote its file). |
| `1` | A map or world file cannot be read or is invalid, the goal is unreachable, the graphical view cannot be used (pygame missing, no display), the simulation fails, an output file cannot be written, standard output was closed early (e.g. `| head`), or an unexpected internal error occurred. One `error: ...` line is printed on standard error. |
| `2` | Invalid command-line arguments (from `argparse`). |
| `130` | Interrupted with Ctrl+C. |

Examples of error messages, taken from real runs:

```text
error: cannot read map file 'nope.txt': No such file or directory
error: line 1: n must be a positive integer, got 0
error: line 3: name must not contain '-', got 'a-b'
error: line 4: zone must be one of normal, blocked, restricted, priority, got 'lava'
error: line 4: unknown zone: x
error: line 4: max_link_capacity must be a positive integer, got 0
error: line 5: duplicate connection: e-s
error: line 2: malformed metadata block
error: line 2: missing end_hub
error: goal 'e' is unreachable from 's'
error: invalid world file 'bad.json': zones: missing start_hub
fly_in.py: error: argument --delay: must be a finite number of seconds >= 0: '-1'
```

## Example

### Input

`maps/subject_example.txt`, the example of the subject:

```text
nb_drones: 5

start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: roof2 6 2 [zone=normal color=blue]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
hub: tunnelB 7 4 [zone=normal color=red]
hub: obstacleX 5 5 [zone=blocked color=gray]
connection: hub-roof1
connection: hub-corridorA
connection: roof1-roof2
connection: roof2-goal
connection: corridorA-tunnelB [max_link_capacity=2]
connection: tunnelB-goal
```

### Output

`make run ARGS="--visual none"` (or
`.venv/bin/python fly_in.py maps/subject_example.txt --visual none`):

```text
D1-corridorA D2-hub-roof1
D1-tunnelB D2-roof1 D3-corridorA D4-hub-roof1
D1-goal D2-roof2 D3-tunnelB D4-roof1 D5-corridorA
D2-goal D3-goal D4-roof2 D5-tunnelB
D4-goal D5-goal
summary: 5 turns, 5 drones, 4.20 turns per drone on average, 3.40 moves per turn
```

The first five lines are the turn log (standard output); the last line is the
summary (standard error). Both routes are 3 turns long: `hub -> corridorA ->
tunnelB -> goal` (through a priority zone) and `hub -> roof1 -> roof2 ->
goal` (entering the restricted `roof1` takes 2 turns, so `D2-hub-roof1` is
the turn D2 spends on the connection). The drones are split over both routes,
and all 5 are delivered in 5 turns.

## Algorithm and implementation strategy

### Pipeline

```text
map file -> MapParser -> World -> Pathfinder (DistanceMap) -> Scheduler
                                                                 |
         TurnLogPrinter, views, RunRecorder  <-  SimulationEngine + TurnResolver
```

1. **Parsing** (`droneflow/parsing`). `MapReader` yields numbered lines.
   `LineTokenizer` checks each line's syntax against `MapFormat`, a
   declarative table of the line kinds, their fields, defaults and
   converters. `MapValidator` converts the fields and asks a list of `Rule`
   objects (unique names, single start and end, known endpoints, unique
   connections) to check what spans several lines. The result is a `World`:
   a hand-built `Network` (zones and an adjacency list) plus the drone count.

2. **Distances** (`droneflow/pathfinding`). `DistanceMap` runs **one
   Dijkstra search from the end zone** (with `heapq`) over the reversed
   connections. Moving into a zone costs that zone's turn cost (1, or 2 for a
   restricted zone); blocked zones are never entered. It gives, for every
   zone, the minimum number of turns to reach the goal. Capacities are
   deliberately ignored here: they change every turn and are the scheduler's
   concern. `Pathfinder` checks that the goal is reachable from the start
   and answers two questions per zone:
   - `next_hops`: the neighbors on a shortest route (entering them plus their
     own distance equals this zone's distance), **priority zones first**,
     then in declaration order;
   - `detour_hops`: the neighbors off the shortest routes from which the goal
     can still be reached, cheapest first.

   The distances and each zone's next hops are computed once per run and
   cached; nothing is recomputed during the simulation.

3. **Scheduling** (`droneflow/simulation/scheduling`). Every turn, the
   `Scheduler` decides one order per drone standing in a zone (no order means
   it waits):
   - drones in flight toward a restricted zone get no order; they land
     automatically;
   - moves planned on earlier turns that are due now are ordered first;
   - the other drones are decided zone by zone in the order of
     `ZoneRanking`: **closest to the goal first** (so drones leaving a zone
     free room before the drones behind ask for it), then zones on the
     priority route, then zones with fewer exits (so a drone with a choice
     does not take the only way out of another), then declaration order;
   - a drone takes the first of its shortest hops that has room according to
     a `TurnLedger`: the connection has capacity this turn, and the zone has
     a seat on the turn the drone enters it and on every later turn with a
     planned move;
   - if none has room, the same hops are tried again letting an `Evictor`
     make room, as a last resort: occupants of the target zone are planned to
     move on along their own shortest hops on a given turn (recursively, if
     their target is full too). This is how a drone can fly to a full
     restricted zone: it must land on the next turn, so an occupant is
     planned to leave on that turn. Planned moves are kept in a
     `ReservationTable` with mark/rollback, so a failed attempt leaves no
     trace;
   - if that fails too, the drone may take a detour allowed by the
     `DetourPolicy`: never into a zone it has already been in, and only when
     it is expected to be no slower than waiting, i.e.
     `turn_cost(v) + distance(v) + queue(v) <= distance(u) + ahead(u)`,
     where `ahead(u)` counts the drones already ahead of it on the shortest
     route and `queue(v)` the drones in and ahead of the detour zone `v`.
     This spreads drones over several paths when the shortest one is
     congested;
   - otherwise the drone waits.

   The scheduler's docstring explains why every run ends: a shortest move
   strictly lowers the drone's distance to the goal, and a detour enters a
   zone the drone has never been in, so each drone makes finitely many moves;
   and at least one drone moves every turn (planned moves and landings always
   happen, and the drone closest to the goal always has room on its shortest
   route).

4. **Rule checking** (`droneflow/simulation`). The `SimulationEngine` runs
   the turn loop. Each turn, the `TurnResolver` lands drones in flight, checks
   every order (an existing, non-blocked, adjacent zone; one order per drone),
   then checks connection capacity on departures and zone capacity on the
   final counts (drones leaving a zone free room for drones entering it in
   the same turn; a drone flying to a restricted zone counts there from the
   turn it lands). Nothing is applied unless the whole turn is legal; an
   illegal turn, a turn where no drone moves, or a turn count above a safety
   limit (`2 * zones * drones`) stops the run with an error. The scheduler is
   therefore never trusted blindly: every printed turn has been checked.

5. **Output** (`droneflow/output`). The engine calls observers after every
   turn: the `TurnLogPrinter` writes and flushes the turn line on standard
   output, the views draw the state, and the optional `RunRecorder` keeps the
   turn for `--save-run`. At the end, `RunSummary` writes the summary line.

**Cost.** With Z zones, C connections and D drones: the Dijkstra search is
O((Z + C) log Z), done once. Each turn, every drone standing in a zone tries
a few hops, each checked against the ledger over the few turns that hold
planned moves; landing and eviction plans only look a few turns ahead. Memory
is O(Z + C + D) for the network, the distances, the cached hops and the
drone positions, plus the planned moves.

### Code structure

```text
fly_in.py                    entry point: arguments, exit codes, error lines
droneflow/
  cli.py                     command-line options (argparse) -> Args
  app.py                     Application: wires the stages together
  errors.py                  FlyInError and its subclasses
  models/                    Zone, ZoneType, ZoneRole, Connection, Drone,
                             Network (hand-built graph), World
  parsing/                   MapReader, LineTokenizer, MapFormat (line table),
                             MapValidator, map rules, MapParser
  pathfinding/               DistanceMap (Dijkstra from the goal), Pathfinder
  simulation/                SimulationState, TurnResolver (rules),
                             SimulationEngine (turn loop), TurnObserver
    scheduling/              Scheduler, ZoneRanking, TurnLedger, HopTaker,
                             Evictor, ReservationTable, DetourPolicy,
                             PositionBoard
  output/                    TurnLogFormatter, TurnLogPrinter, RunSummary
  visualization/             TerminalVisualizer, GraphicalVisualizer (pygame),
                             camera, geometry, labels, palette
  interchange/               JSON world files and run files
```

Design choices visible in the code:

- **Composition is preferred to inheritance.** The `Application` composes the stages;
  the engine composes a state, a `TurnResolver` (the rules) and a
  `MoveDecider` (the `Scheduler`); the scheduler delegates to small classes
  (ledger, evictor, detour policy, ranking).
- **Protocols for the seams.** `MoveDecider`, `TurnObserver` and `Rule` are
  `typing.Protocol`s, so the turn log printer, the views and the run recorder
  are all observers of the same engine, and another decider can be plugged
  into the `Application`.
- **The rules are separate from the decisions.** The scheduler plans; the
  resolver checks and applies. A scheduling bug becomes a clear
  `SimulationError` instead of an invalid turn log.
- **Only one module imports pygame** (`visualization/graphical_view.py`), and
  it is imported lazily, so the rest works without pygame.

## Visual representation

The subject asks for visual feedback through colored terminal output, a
graphical interface, or both. Both are provided, selected with `--visual`.

### Terminal view

The default view (`--visual terminal`) writes one frame per turn to standard
error, so it never mixes with the turn log on standard output. Each frame
has:

- a header with the turn number, the number of moves, and the delivered
  count;
- the turn's moves;
- a grid of every zone with a one-letter tag (`S` start, `E` end, `.` normal,
  `P` priority, `R` restricted, `X` blocked) and its load `inside/capacity`
  (`-` for no limit), `+N` for drones flying toward it, and `*` when it is
  full;
- where the drones are (consecutive numbers shortened as `D1..D5`) and which
  drones are in flight, on which connection, toward which zone.

Zone names are painted with their `color=` metadata (24-bit ANSI colors);
unknown color names fall back to the terminal's default color, full counts
are bold, and blocked zones are dimmed. Colors are turned off when standard
error is not a terminal or when `NO_COLOR` is set. With `--step`, each frame
waits for Enter. The terminal width sets how many zones fit on a line, and
long names are shortened with `~`.

The initial state and the first two turns of the example (`NO_COLOR=1`, 100 columns):

```text
=== Turn 0 (start) | 5 drones | 7 zones, 6 connections ===
key: S=start E=end .=normal P=priority R=restricted X=blocked | in/max: -=no limit +N=arriving *=full
  hub       S 5/-        goal      E 0/-        roof1     R 0/1        roof2     . 0/1
  corridorA P 0/2        tunnelB   . 0/1        obstacleX X --
drones: hub[D1..D5]
=== Turn 1 | moved 2 | delivered 0/5 ===
moves: D1-corridorA D2-hub-roof1
  hub       S 3/-        goal      E 0/-        roof1     R 0/1+1*     roof2     . 0/1
  corridorA P 1/2        tunnelB   . 0/1        obstacleX X --
drones: corridorA[D1] hub[D3..D5]
in flight: D2 hub-roof1 -> roof1
=== Turn 2 | moved 4 | delivered 0/5 ===
moves: D1-tunnelB D2-roof1 D3-corridorA D4-hub-roof1
  hub       S 1/-        goal      E 0/-        roof1     R 1/1+1*     roof2     . 0/1
  corridorA P 1/2        tunnelB   . 1/1*       obstacleX X --
drones: tunnelB[D1] roof1[D2] corridorA[D3] hub[D5]
in flight: D4 hub-roof1 -> roof1
```

`roof1 R 1/1+1*` shows a restricted zone that is about to be left by D2 and
entered by D4 on the same turn, which is legal; the view makes that visible
instead of looking like an overflow.

### Graphical view

`--visual graphical` (or `both`, together with the terminal view) opens a
1200x800 pygame window that draws the network at the zones' coordinates (y
pointing up) and plays the run, one turn every `--delay` seconds.

What is drawn:

- **Zones** filled with their `color=` (the palette, then pygame's color
  names, then a default gray). Normal zones are circles; priority zones have
  a gold ring; the start and end zones a white ring and `(start)` / `(end)`
  after their name; restricted zones are squares with a red ring; blocked
  zones are dark gray with a cross.
- **Load bars** under each zone with a capacity: green, orange, then red as
  the zone fills, with a pale part for the drones arriving next turn, and a
  label `occupancy/capacity +N`. The end zone shows how many drones were
  delivered.
- **Connections** as lines whose width grows with `max_link_capacity`
  (labelled `xN` when above 1), brighter while a drone is flying on them.
  Zones that share a position are spread around it, and a connection that
  would run over another zone is drawn as an arc around it.
- **Drones** as dots: white in a zone, cyan when on a connection (drawn at
  its middle, toward a restricted zone), with a gold ring if they moved this
  turn. Several drones at one point are one badge with their count. Each
  move of the turn leaves a gold **trail** along the connection it used.
- A **status bar** with the turn, the moves, the delivered count and the
  drones in flight, the controls and the current delay; a **footer** with
  the turn's moves (`... +K more` when they do not fit); and a **tooltip**
  with the full details of the zone under the mouse (role, type, color,
  load, drone numbers).

Controls:

| Input | Effect |
| --- | --- |
| Space | Pause / resume. |
| Right arrow | Next turn now, without waiting for the delay (also while paused and in step mode). |
| Up / `+` | Faster (halves the delay; below 0.05 s it goes to 0, no wait). |
| Down / `-` | Slower (doubles the delay, from 0.05 s when it is 0, up to 60 s like `--delay`). |
| Mouse wheel | Zoom around the mouse (from 0.5x up to a zoom where the closest zones are readable). Zones and text keep their size; only the distances grow. |
| Left drag | Move the map. |
| `f` | Fit the whole map again. |
| Esc, `q`, close button | Close the window. |

With `--step`, the window starts paused and the right arrow plays one turn
at a time. After the last turn the window stays open with "finished - press
esc to close". Closing the window early only closes the view: the simulation
goes on to the end, so the turn log on standard output is still complete. On
large maps, zones shrink to dots and labels are left out when zoomed out too
far to read them; zooming in brings them back.

If pygame is not installed, or no window can be opened (e.g. no display),
the program stops with one error line and exit code 1, for example
`error: the graphical view needs pygame (pygame-ce): run 'make install' or
'pip install pygame-ce', or use --visual terminal`.

## Additional features

- **Stages on their own, through readable JSON files.**
  `--parse-only world.json` stops after the parser and writes the parsed
  world (every zone and connection with every field, in declaration order);
  `--from-world` simulates such a file without the parser (it is checked
  with the same rules as a map, so a file edited by hand cannot give the
  simulation a map the parser would reject); `--save-run run.json` writes,
  for every turn (turn 0 is the initial state), the log line, each move, the
  delivered count and where every undelivered drone is. If the run fails,
  the turns played so far are written with `"complete": false`.

  ```text
  $ .venv/bin/python fly_in.py maps/subject_example.txt --parse-only world.json
  world: wrote world.json (7 zones, 6 connections, 5 drones)
  $ .venv/bin/python fly_in.py world.json --from-world --visual none --save-run run.json
  D1-corridorA D2-hub-roof1
  ...
  run: wrote run.json
  summary: 5 turns, 5 drones, 4.20 turns per drone on average, 3.40 moves per turn
  ```

- **Run summary** on standard error with the subject's secondary metrics
  (average turns per drone, moves per turn).
- **Step mode** (`--step`) in both views, and adjustable speed, pause, zoom,
  pan and hover details in the graphical view.
- **Clean streams**: the turn log is flushed line by line on standard
  output and nothing else is written there (pygame's import banner is
  hidden), so it can be piped or redirected; a reader that closes early
  (`| head`) does not cause a traceback.
- **Robust error handling**: every expected failure is one `error: ...` line
  with a non-zero exit code; unexpected exceptions become one
  `error: internal error: ...` line, unless `FLYIN_DEBUG=1` (`make debug`).

## Testing and quality

- `make lint` and `make lint-strict` pass: running the same commands
  (`flake8 .`, `mypy .` with the subject's flags, and `mypy . --strict`) on
  this repository reports no issues (flake8 7.4, mypy 2.4, Python 3.14).
- Classes and public functions have Google-style docstrings, and the code is
  fully type-annotated (checked by `mypy --strict`).
- At run time, the `TurnResolver` checks every turn against the movement and
  capacity rules before applying it, so a printed turn log is always a legal
  one; the engine also stops if no drone moves in a turn or a safety turn
  limit is exceeded.
- `make test` runs the unit tests in `tests/` (pytest; the graphical view's
  tests run headless and are skipped when pygame-ce is not installed). The
  `tests/` folder is kept on the development branch only; the submitted
  branch has no tests.
- The behaviour shown in this README (example output, terminal view, error
  messages, JSON files) was also checked by running the program on the
  subject example and on small hand-written maps.

## Resources

### References

- The Fly-in subject (42, version 1.6): rules, map format, output format
  and benchmarks.
- [Dijkstra's algorithm](https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm)
  (Wikipedia), used here from the end zone with zone-dependent costs.
- [Python `heapq`](https://docs.python.org/3/library/heapq.html): the
  priority queue of the search.
- [Python `argparse`](https://docs.python.org/3/library/argparse.html),
  [`dataclasses`](https://docs.python.org/3/library/dataclasses.html),
  [`typing.Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol).
- [pygame-ce documentation](https://pyga.me/docs/): the graphical view.
- [mypy](https://mypy.readthedocs.io/) and
  [flake8](https://flake8.pycqa.org/): static checks.
- [PEP 257](https://peps.python.org/pep-0257/) (docstrings) and the
  [Google Python style guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
- [ANSI escape codes](https://en.wikipedia.org/wiki/ANSI_escape_code) and
  [NO_COLOR](https://no-color.org): the terminal view's colors.

### How AI was used

An AI assistant (Claude) was used throughout the project, under the
developer's direction: to analyse the subject's requirements, to discuss
design options (parser structure, pathfinding, scheduling, views), to review
code and find bugs, and to write code as instructed. It also helped write
this README from the code and real runs of the program. The developer
reviewed all of the code and is responsible for it.
