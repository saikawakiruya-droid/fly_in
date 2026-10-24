*This project has been created as part of the 42 curriculum by naarai.*

# Fly-in

> **Minimal variant (experimental branch `feature/minimal_build`).** This
> branch keeps only what the subject makes mandatory: the parser and its
> validation, the pathfinding and scheduling, the rule-checked simulation, the
> turn log in the required format, and a colored terminal view. The graphical
> window, the extra command-line options (`--visual`, `--delay`, `--step`,
> `--parse-only`, `--from-world`, `--save-run`), the JSON files, the summary
> line and the debug switch of the full version were removed. The turn log is
> the same as the full version's on every map.
>
> **Variant `feature/minimal_matplotlib`.** On top of that, a single
> `--graphical` option adds a minimal matplotlib window (zones, connections,
> drones turn by turn, the turn number), and the final summary line of the
> full version is back on standard error. The turn log on standard output is
> the same as `feature/minimal_build`'s.

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
the terminal with colors (and, with `--graphical`, in a matplotlib window).
No graph library is used: the graph, the
shortest-path search and the scheduler are written by hand, as the subject
requires. The code is object-oriented, type-annotated, and passes `flake8`
and `mypy --strict`.

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

Everything else goes to standard error: the terminal view, errors, and a
final summary line with the total number of turns and two of the subject's
secondary metrics (average delivery turn per drone, average moves per turn):

```text
summary: 5 turns, 5 drones, 4.20 turns per drone on average, 3.40 moves per turn
```

So `python3 fly_in.py map.txt 2>/dev/null` prints exactly the required output.

## Instructions

### Requirements

- Python 3.10 or later (the checks below were run with Python 3.14).
- `matplotlib` (>= 3.8) for the `--graphical` window only.
- `flake8` and `mypy` for `make lint` / `make lint-strict`.
- `pytest` for `make test` (the unit tests in `tests/`).

All of them are listed in `requirements.txt`; without `--graphical` the
program needs only the standard library. The Makefile is written for Linux (it uses
`.venv/bin/python`).

The maps handed out with the subject (`maps.tar.gz`) are not part of the
submitted repository; download the archive from the subject page and extract
it, e.g. with `tar -xzf maps.tar.gz`. Only `maps/subject_example.txt` (the
example of the subject) is included.

### Makefile

| Rule | What it does |
| --- | --- |
| `make install` | Creates `.venv` (if it is absent or has no working pip) and installs `requirements.txt` into it. |
| `make run` | Runs `maps/subject_example.txt`. Override the map with `MAP=`, e.g. `make run MAP=path/to/map.txt`. |
| `make debug` | The same run under `pdb`. |
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
.venv/bin/python fly_in.py MAP [--graphical]
```

The map file is the only required argument (`-h` shows the usage).
`--graphical` also shows the run in a matplotlib window (see "Visual
representation"); the turn log and the terminal view are unchanged.

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
| `0` | The run finished. |
| `1` | The map file cannot be read or is invalid, the goal is unreachable, the simulation fails, `--graphical` cannot open a window (matplotlib missing, no display), or an unexpected internal error occurred. One `error: ...` line is printed on standard error. |
| `2` | Invalid command-line arguments (from `argparse`). |
| `130` | Interrupted with Ctrl+C. |

Examples of error messages:

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
error: cannot open the graphical window (no display?)
fly_in.py: error: unrecognized arguments: --visual none
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

`.venv/bin/python fly_in.py maps/subject_example.txt 2>/dev/null` (standard
output only):

```text
D1-corridorA D2-hub-roof1
D1-tunnelB D2-roof1 D3-corridorA D4-hub-roof1
D1-goal D2-roof2 D3-tunnelB D4-roof1 D5-corridorA
D2-goal D3-goal D4-roof2 D5-tunnelB
D4-goal D5-goal
```

Both routes are 3 turns long: `hub -> corridorA -> tunnelB -> goal` (through
a priority zone) and `hub -> roof1 -> roof2 -> goal` (entering the restricted
`roof1` takes 2 turns, so `D2-hub-roof1` is the turn D2 spends on the
connection). The drones are split over both routes, and all 5 are delivered
in 5 turns.

## Algorithm and implementation strategy

### Pipeline

```text
map file -> MapParser -> World -> Pathfinder (DistanceMap) -> Scheduler
                                                                 |
        TurnLogPrinter, TerminalVisualizer  <-  SimulationEngine + TurnResolver
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

5. **Output** (`droneflow/output`, `droneflow/visualization`). The engine
   calls its observers after every turn: the `TurnLogPrinter` writes and
   flushes the turn line on standard output, and the `TerminalVisualizer`
   draws the state on standard error. At the end, `RunSummary` writes the
   summary line.

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
  cli.py                     the map argument (argparse) -> Args
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
  visualization/             palette (color names, shared by both views)
    terminal/                TerminalVisualizer
    graphical/               GraphicalVisualizer and MapScene (matplotlib),
                             geometry (where connections are drawn)
```

Design choices visible in the code:

- **Composition is preferred to inheritance.** The `Application` composes the stages;
  the engine composes a state, a `TurnResolver` (the rules) and a
  `MoveDecider` (the `Scheduler`); the scheduler delegates to small classes
  (ledger, evictor, detour policy, ranking).
- **Protocols for the seams.** `MoveDecider`, `TurnObserver` and `Rule` are
  `typing.Protocol`s, so the turn log printer and the terminal view are both
  observers of the same engine, and another decider can be plugged into the
  `Application`.
- **The rules are separate from the decisions.** The scheduler plans; the
  resolver checks and applies. A scheduling bug becomes a clear
  `SimulationError` instead of an invalid turn log.

## Visual representation

The subject asks for visual feedback through colored terminal output, a
graphical interface, or both. This variant provides the colored terminal
output, and a minimal graphical window with `--graphical`.

The terminal view writes one frame per turn to standard error, so it never
mixes with the turn log on standard output. Each frame has:

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
error is not a terminal or when `NO_COLOR` is set. The terminal width sets
how many zones fit on a line, and long names are shortened with `~`. Seeing
the loads, the drones in flight and the moves of each turn side by side makes
it easy to follow why a drone waits or takes a detour.

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

### Graphical window (`--graphical`)

The window (matplotlib) draws the map once and then the drones, one turn
every 0.5 seconds:

- zones are circles filled with their `color=`; restricted zones are
  squares, blocked zones are dark gray, and the ring marks the start and end
  (white), restricted (red) and priority (gold) zones; names are written
  under the zones on maps of up to 60 zones;
- connections are straight lines, bent into an arc only where the straight
  line would cross another zone. Zones are drawn in map units with the same
  radius the arcs are routed round, and x and y keep the same scale, so a
  connection is curved exactly when it would otherwise run over a zone on
  screen. Zooming in with matplotlib's toolbar makes the zones bigger;
- a drone is a white dot in its zone, or a cyan dot in the middle of the
  connection while it flies to a restricted zone (that connection is drawn
  cyan and twice as thick); several drones at the same point are one bigger dot holding their
  number. The title shows the turn
  number and the delivered count.

Closing the window stops the drawing; the simulation then finishes at once,
so the turn log is still complete. After the last turn the window stays open
until it is closed. Without a display, the program stops with
`error: cannot open the graphical window (no display?)`.

## Testing and quality

- `make lint` and `make lint-strict` pass: `flake8 .`, `mypy .` with the
  subject's flags, and `mypy . --strict` report no issues (flake8 7.4,
  mypy 2.4, Python 3.14).
- Classes and public functions have Google-style docstrings, and the code is
  fully type-annotated (checked by `mypy --strict`).
- At run time, the `TurnResolver` checks every turn against the movement and
  capacity rules before applying it, so a printed turn log is always a legal
  one; the engine also stops if no drone moves in a turn or a safety turn
  limit is exceeded.
- `make test` runs the unit tests in `tests/` (pytest).

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
- [mypy](https://mypy.readthedocs.io/) and
  [flake8](https://flake8.pycqa.org/): static checks.
- [PEP 257](https://peps.python.org/pep-0257/) (docstrings) and the
  [Google Python style guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
- [ANSI escape codes](https://en.wikipedia.org/wiki/ANSI_escape_code) and
  [NO_COLOR](https://no-color.org): the terminal view's colors.
- [matplotlib](https://matplotlib.org/): the graphical window (patches,
  collections, `set_aspect("equal")`), and
  [Bezier curves](https://en.wikipedia.org/wiki/B%C3%A9zier_curve) for the
  arcs.

### How AI was used

An AI assistant (Claude) was used throughout the project, under the
developer's direction: to analyse the subject's requirements, to discuss
design options (parser structure, pathfinding, scheduling, views), to review
code and find bugs, and to write code as instructed. This minimal variant was
produced by the assistant, at the developer's request, by removing the
non-mandatory features from the full version, and then added the minimal
`--graphical` window on branch `feature/minimal_matplotlib`. It also helped write this
README from the code and real runs of the program. The developer reviews all
of the code and is responsible for it.
