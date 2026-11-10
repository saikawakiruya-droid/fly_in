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

The program parses and validates the map, finds the routes the drones take
and how many each route takes per turn, moves every drone along its route
turn by turn, checks every turn against
the rules, prints the turn log in the required format, and, when asked,
shows the run in the terminal with colors (`--terminal-view`) or in a window
(`--matplotlib-window`).
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
| `nb_drones: <n>` | Number of drones, a positive integer. **Must be the first line that is not a comment or blank.** |
| `start_hub: <name> <x> <y> [metadata]` | The start zone (exactly one). |
| `end_hub: <name> <x> <y> [metadata]` | The end zone (exactly one). |
| `hub: <name> <x> <y> [metadata]` | A regular zone. |
| `connection: <name1>-<name2> [metadata]` | A bidirectional connection between two zones declared earlier. |
| `# ...` | A comment line (only whole lines; a `#` after a declaration is an error). Blank lines are ignored too. |

Zone metadata (optional, any order): `zone=normal|blocked|restricted|priority`
(default `normal`), `color=<word>` (default none), `max_drones=<n>` (default 1).
Connection metadata: `max_link_capacity=<n>` (default 1).

The parser stops at the first problem and reports the line and the cause.
It rejects, among others: a first line (after comments and blank lines)
that is not `nb_drones:`, a
non-positive drone count or capacity, a non-integer coordinate, an unknown
zone type, an unknown or repeated metadata key, a malformed `[...]` block, a
zone name containing `-`, a duplicate zone name, a second `start_hub` or
`end_hub`, a connection to a zone not declared yet, a connection from a zone
to itself (`a-a`), a duplicate connection (`a-b` and `b-a` are the same),
and a missing `start_hub` or `end_hub`.
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

Everything else goes to standard error: errors, the terminal view (only
with `--terminal-view`), and a final summary line with the total number of
turns and two of the subject's secondary metrics (average delivery turn per drone, average moves per turn):

```text
summary: 5 turns, 5 drones, 4.20 turns per drone on average, 3.40 moves per turn
```

So `python3 fly_in.py map.txt 2>/dev/null` prints exactly the required output.

## Instructions

### Requirements

- Python 3.10 or later (the checks below were run with Python 3.14).
- `matplotlib` (>= 3.8) for `--matplotlib-window` only. On Linux the
  window also needs Tk (e.g. the `python3-tk` package) and a display.
- `flake8` and `mypy` for `make lint` / `make lint-strict`.

All of them are listed in `requirements.txt`; without `--matplotlib-window` the
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
| `make clean` | Removes `__pycache__`, `.mypy_cache`, `.pytest_cache` and `*.pyc` / `*.pyo` files (outside `.venv`). |
| `make fclean` | `clean`, then removes `.venv`. |

`run`, `debug`, `lint` and `lint-strict` run `make install` first when
`.venv` has not been installed yet or `requirements.txt` changed.

### Running directly

```sh
make install
.venv/bin/python fly_in.py MAP [--terminal-view] [--matplotlib-window]
```

The map file is the only required argument (`-h` shows the usage). Each view
is used only when its option is given (see "Visual representation"), and the
two can be combined; the turn log on standard output is the same either way:

- `--terminal-view` draws each turn in the terminal, on standard error;
- `--matplotlib-window` shows the run in a matplotlib window.

**Maps that start with comments.** The parser skips comments and blank
lines before the `nb_drones:` header (the subject: "The first line must
define the number of drones"), so the maps distributed with the subject,
which begin with comment lines, run as they are:

```sh
make run MAP=path/to/maps/easy/01_linear_path.txt
```

Any other line before the header is an error, reported on its line:

```text
$ .venv/bin/python fly_in.py hub_first.txt
error: line 2: the first line that is not a comment must be 'nb_drones: <n>'
```

### Exit codes

| Code | When |
| --- | --- |
| `0` | The run finished. |
| `1` | The map file cannot be read or is invalid, the goal is unreachable, the simulation fails, `--matplotlib-window` cannot open a window (matplotlib missing, no display), or an unexpected internal error occurred. One `error: ...` line is printed on standard error. |
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
error: line 5: a connection must join two different zones, got a-a
error: line 5: duplicate connection: e-s
error: line 2: malformed metadata block
error: line 2: missing end_hub
error: goal 'e' is unreachable from 's'
error: cannot open the matplotlib window (no display?)
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
map file -> MapParser -> World -> Pathfinder (FlowMap) -> Scheduler
                                                                 |
     TurnLogPrinter (+ the views asked for)  <-  SimulationEngine + TurnResolver
```

1. **Parsing** (`map_parser.py`, `map_parser_format.py`). `MapReader` yields numbered lines.
   `LineTokenizer` checks each line's syntax against `MapFormat`, a
   declarative table of the line kinds, their fields, defaults and
   converters. `MapValidator` converts the fields and asks a list of `Rule`
   objects (unique names, single start and end, known endpoints, unique
   connections) to check what spans several lines. The result is a `World`:
   a hand-built `Network` (zones and an adjacency list) plus the drone count.

2. **Routes** (`pathfinder.py`). The `Pathfinder` builds a **flow map**
   once, before the first turn: the routes the drones take, and how many
   drones each route takes per turn. The drones flow like a steady stream:
   if each route never takes more drones per turn than every zone and
   connection on it can pass on, no drone ever waits after leaving the start
   zone. The routes are found with a **minimum cost flow** (successive
   shortest paths) on the `FlowGraph`, a residual graph written by hand:
   - each zone is two nodes, "in" and "out", joined by an arc of capacity
     `max_drones`; each connection gives an arc of capacity
     `max_link_capacity` in each direction; entering a zone costs its turn
     cost (1, or 2 for a restricted zone); blocked zones get no nodes;
   - a priority zone costs slightly less, so that among equally fast routes
     the one through priority zones is taken (never at the price of a turn);
   - back arcs cost less than nothing, so the shortest path search is
     Bellman-Ford with a queue.

   A route of `turns` turns that takes `rate` drones per turn has delivered
   `rate * (T - turns + 1)` drones by turn `T`, so the last drone arrives on
   the first turn `T` where the routes together have delivered them all.
   Each shortest path found adds drones per turn but may be longer, so paths
   are added while `T` goes down (sending a fixed flow this way is optimal
   for one start and one end: Ford and Fulkerson's temporally repeated
   flows). The result is a `FlowMap`: the **held map**, a `Network` cut down
   to the zones and connections the routes use, whose capacities are the
   drones per turn the routes send through them, plus the routes and `T`.
   `Pathfinder` also checks that the goal is reachable from the start.

3. **Scheduling** (`scheduler.py`). `plan_departures` gives every drone a
   route and a turn to leave the start zone on: each route has `rate` seats
   per turn, and the drones take the seats that arrive first. A longer route
   is therefore taken only when waiting for a seat on a shorter one would
   arrive later. Every turn, the `Scheduler` visits the zones of the held
   map **nearest to the goal first**, and each zone **pulls** the drones
   whose next zone on their route it is: drones in the start zone whose turn
   has come, and every drone already on its way. Drones in flight toward a
   restricted zone get no order; they land automatically. Each pull is
   checked against the held map: the drone has never been in the zone (each
   `Drone` keeps the `history` of the zones it has been in), and the
   connection and the zone still have room this turn. The checks always pass
   when the flow map is right; if one fails, a `SimulationError` is raised
   instead of breaking a rule. Every run ends: each drone makes as many
   moves as its route has steps.

4. **Rule checking** (`engine.py`). The `SimulationEngine` runs
   the turn loop. Each turn, the `TurnResolver` lands drones in flight, checks
   every order (an existing, non-blocked, adjacent zone; one order per drone),
   then checks connection capacity on departures and zone capacity on the
   final counts (drones leaving a zone free room for drones entering it in
   the same turn; a drone flying to a restricted zone counts there from the
   turn it lands). Nothing is applied unless the whole turn is legal; an
   illegal turn, a turn where no drone moves, or a turn count above a safety
   limit (`2 * zones * drones`) stops the run with an error. The scheduler is
   therefore never trusted blindly: every printed turn has been checked.

5. **Output** (`turn_log_printer.py`, `terminal_view.py`,
   `matplotlib_window.py`). The engine calls its observers after every turn:
   the `TurnLogPrinter` writes and flushes the turn line on standard output,
   and the views asked for on the command line draw the state. At the end,
   `RunSummary` writes the summary line.

**Cost.** With Z zones, C connections and D drones: the flow map is built
once, with at most one shortest path search (Bellman-Ford, O(Z * C)) per
route added, and there are at most D routes. Each turn, every drone standing
in a zone is pulled at most once, with constant-time checks. Memory is
O(Z + C + D) for the network, the held map, the routes and the drones'
departures and histories.

### Code structure

```text
fly_in.py                       entry point: exit codes and error lines
app.py                          Args (the command line) and Application, which
                                wires the files below together
errors.py                       FlyInError and its subclasses
world.py                        Zone, Connection, Network (the hand-built graph),
                                World
map_parser.py                   MapReader, LineTokenizer, MapValidator, MapParser
map_parser_format.py            MapFormat (the table of line kinds) and the rules
                                that span several lines
pathfinder.py                   Route, FlowMap (the held map), FlowGraph (the
                                minimum cost flow), Pathfinder
engine.py                       Drone, SimulationState, TurnResolver (the rules),
                                TurnObserver, SimulationEngine (the turn loop)
scheduler.py                    Departure, plan_departures, Scheduler (pulls
                                the drones along the flow map)
turn_log_printer.py             TurnLogFormatter, TurnLogPrinter, RunSummary
terminal_view.py                TerminalVisualizer and its color names
                                (--terminal-view)
matplotlib_window.py            MatplotlibWindowVisualizer, MapScene and the plane
                                geometry (--matplotlib-window)
```

Every source file is at the root of the repository, as the subject asks.
Each file holds one part of the program with the classes it delegates to,
defined in the order they are used: the classes a file needs come first,
and the one the rest of the program uses is last; the file's docstring
lists them. The biggest part is split in two, and the second file is named
after the first (`map_parser_format.py` holds the parser's tables). Each
view is one file.

Design choices visible in the code:

- **Composition is preferred to inheritance.** The `Application` composes the stages;
  the engine composes a state, a `TurnResolver` (the rules) and a
  `MoveDecider` (the `Scheduler`); the scheduler gets its routes from the
  `Pathfinder`, which builds them on a `FlowGraph`.
- **Protocols for the seams.** `MoveDecider`, `TurnObserver` and `Rule` are
  `typing.Protocol`s, so the turn log printer and the terminal view are both
  observers of the same engine, and another decider can be plugged into the
  `Application`.
- **The rules are separate from the decisions.** The pathfinder and the
  scheduler plan; the
  resolver checks and applies. A scheduling bug becomes a clear
  `SimulationError` instead of an invalid turn log.

## Visual representation

The subject asks for visual feedback through colored terminal output, a
graphical interface, or both. This program provides both, each behind its
own option: the colored terminal output with `--terminal-view`, and a
simple matplotlib window with `--matplotlib-window`.

### Terminal view (`--terminal-view`)

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
it easy to follow which route each drone takes and when it leaves.

The initial state and the first two turns of the example
(`NO_COLOR=1 .venv/bin/python fly_in.py --terminal-view maps/subject_example.txt`,
100 columns):

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

### Matplotlib window (`--matplotlib-window`)

The window (matplotlib) draws the map once and then the drones, one turn
every 0.5 seconds:

- zones are circles filled with their `color=` (matplotlib's color names;
  an unknown name is drawn gray); restricted zones are
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
`error: cannot open the matplotlib window (no display?)`.

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
- The repository contains no unit tests. The behaviour shown in this README
  (example output, terminal view, error messages) was checked by running the
  program on the subject example and on small hand-written maps.

## Resources

### References

- The Fly-in subject (42, version 2.0): rules, map format, output format
  and the optimal turn counts of the provided maps.
- [Minimum-cost flow problem](https://en.wikipedia.org/wiki/Minimum-cost_flow_problem)
  and the [Bellman-Ford algorithm](https://en.wikipedia.org/wiki/Bellman%E2%80%93Ford_algorithm)
  (Wikipedia): the successive shortest paths that find the routes.
- L. R. Ford and D. R. Fulkerson, "Constructing maximal dynamic flows from
  static flows", Operations Research 6(3), 1958: sending a fixed flow over
  time (temporally repeated flows), and why it is optimal for one source and
  one sink.
- [Python `argparse`](https://docs.python.org/3/library/argparse.html),
  [`dataclasses`](https://docs.python.org/3/library/dataclasses.html),
  [`typing.Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol).
- [mypy](https://mypy.readthedocs.io/) and
  [flake8](https://flake8.pycqa.org/): static checks.
- [PEP 257](https://peps.python.org/pep-0257/) (docstrings) and the
  [Google Python style guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
- [ANSI escape codes](https://en.wikipedia.org/wiki/ANSI_escape_code) and
  [NO_COLOR](https://no-color.org): the terminal view's colors.
- [matplotlib](https://matplotlib.org/): the window (patches,
  collections, `set_aspect("equal")`), and
  [Bezier curves](https://en.wikipedia.org/wiki/B%C3%A9zier_curve) for the
  arcs.

### How AI was used

An AI assistant (Claude) was used throughout the project, under the
developer's direction: to analyse the subject's requirements, to discuss
design options (parser structure, pathfinding, scheduling, views), to review
code and find bugs, and to write code as instructed. At the developer's
request, the assistant also removed the non-mandatory features from an
earlier, larger version of the program and wrote the simple matplotlib
window of `--matplotlib-window`. It also helped write this
README from the code and real runs of the program. The developer reviews all
of the code and is responsible for it.
