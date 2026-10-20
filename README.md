*This project has been created as part of the 42 curriculum by naarai.*

# Fly-in

A turn-based simulation that routes a fleet of drones through a network of
zones, from a start zone to an end zone, in as few turns as possible, while
respecting zone capacities, connection capacities and multi-turn moves into
restricted zones.

Japanese version: [README.ja.md](README.ja.md)

## Description

The program reads a map file describing a graph of zones (with coordinates,
types, colors and capacities) and the connections between them, places
`nb_drones` drones in the start zone, and plays the simulation turn by turn
until every drone has been delivered to the end zone. Each turn is printed as
one line listing the drones that moved, in the format required by the subject.

The project is written in Python, is fully object-oriented and type-annotated
(it passes `flake8` and `mypy --strict`), and implements all graph logic by
hand: no graph library (networkx, graphlib, ...) is used.

Main features:

- A parser that validates the whole input format and stops with a one-line
  error naming the line and the cause.
- A goal-rooted Dijkstra distance map, computed once, that tells every drone
  which moves keep it on a shortest route.
- A per-turn scheduler that moves as many drones as the capacities allow,
  with a reservation table and an eviction mechanism for restricted zones.
- An independent rule checker that validates every turn before applying it.
- Two views: a colored terminal view and a graphical window (pygame-ce), which
  can also be used together.

### Input format

```text
nb_drones: <positive integer>
start_hub: <name> <x> <y> [metadata]
end_hub: <name> <x> <y> [metadata]
hub: <name> <x> <y> [metadata]
connection: <zone1>-<zone2> [metadata]
```

- Zone metadata: `zone=normal|blocked|restricted|priority` (default `normal`),
  `color=<word>` (any single word), `max_drones=<positive integer>`
  (default 1; ignored on the start and end zones, which have no limit).
- Connection metadata: `max_link_capacity=<positive integer>` (default 1).
- Lines starting with `#` are comments; blank lines are ignored.
- Entering a zone costs 1 turn (`normal`, `priority`) or 2 turns
  (`restricted`); `blocked` zones can never be entered.

**Input constraint: `nb_drones: <n>` must be on the physical first line of the
file.** The subject states that "the first line must define the number of
drones", and this program reads it literally: a comment or a blank line before
`nb_drones:` is a parse error.

```text
$ python fly_in.py map_with_a_comment_first.txt
error: line 1: the first line must be 'nb_drones: <n>'
```

Comments and blank lines are accepted anywhere after the first line.

### Output format

One line per turn, listing only the drones that moved during that turn, in
drone id order:

- `D<id>-<zone>`: the drone entered `<zone>` (delivered drones disappear from
  the following lines);
- `D<id>-<zone1>-<zone2>`: the drone took off toward a restricted zone and is
  on that connection (named as declared in the map); it lands on the next turn.

## Instructions

### Requirements

- Python 3.10 or later (the subject's requirement). The project was developed
  and tested with Python 3.14.
- `make`, and the packages in `requirements.txt`:
  - `pygame-ce` for the graphical view. pygame-ce is a maintained fork of
    pygame that is imported as `pygame`; it is used because pygame itself
    publishes no wheels for Python 3.14. The terminal view and the simulation
    do not need it.
  - `flake8`, `mypy` (lint) and `pytest` (unit tests).

### Makefile

| Command | What it does |
|---|---|
| `make install` | Create `.venv` if it does not exist and install `requirements.txt` into it |
| `make run` | Run the default map (`maps/subject_example.txt`) |
| `make run MAP=path/to/map.txt ARGS="--visual both"` | Run another map, with extra options |
| `make debug` | The same as `run`, under `pdb` (see below) |
| `make clean` | Remove caches (`__pycache__`, `.mypy_cache`, `.pytest_cache`, `*.pyc`) |
| `make fclean` | `clean`, and remove `.venv` as well |
| `make lint` | `flake8 .` and `mypy .` with the flags required by the subject |
| `make lint-strict` | `flake8 .` and `mypy . --strict` |
| `make test` | Run the unit tests (`pytest tests -q`) |

`run`, `debug`, `lint`, `lint-strict` and `test` run `install` first when the
virtual environment is missing or older than `requirements.txt`. The Makefile
uses `.venv/bin` on Linux/macOS and `.venv/Scripts` on Windows.

`make debug` sets `FLYIN_DEBUG=1` and starts the program with
`python -m pdb`. Normally an unexpected exception (a bug) is reported as a
single `error: internal error: ...` line; with `FLYIN_DEBUG=1` it propagates,
so pdb stops at it for post-mortem inspection.

### Running directly

```text
python fly_in.py MAP [--visual {terminal,graphical,both,none}] [--delay SECONDS] [--step]
```

| Option | Meaning |
|---|---|
| `MAP` | The map file to simulate |
| `--visual terminal` | Colored terminal view (default) |
| `--visual graphical` | Graphical window (needs pygame-ce) |
| `--visual both` | Both views at the same time |
| `--visual none` | No view: only the turn log and the summary |
| `--delay SECONDS` | Seconds per turn in the graphical view, from 0 to 60 (default 0.5) |
| `--step` | Advance one turn at a time: Enter in the terminal view, the right arrow in the graphical view (with `both`, the window drives the steps) |

`--delay` is ignored outside the graphical view, and `--step` with
`--visual none`.

Standard output always contains **only the turn log**, in every mode, so it can
be redirected or piped and checked as it is. Everything else (the terminal
view, the final summary, warnings and errors) goes to standard error.

### Exit codes

| Code | When |
|---|---|
| 0 | Every drone was delivered |
| 1 | The map file cannot be read, is invalid, or its goal is unreachable; the simulation failed; the graphical view cannot be used; an unexpected internal error; standard output was closed early (e.g. `\| head`) |
| 2 | Invalid command-line arguments (argparse usage error) |
| 130 | Interrupted with Ctrl+C |

Examples of error messages (one line on standard error, no traceback):

```text
error: line 4: zone must be one of normal, blocked, restricted, priority, got 'lava'
error: goal 'g' is unreachable from 's'
error: cannot read map file 'nofile.txt': No such file or directory
fly_in.py: error: argument --delay: must be between 0 and 60 seconds: '61'
```

## Example

### Input: the example map of the subject (`maps/subject_example.txt`)

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

```text
$ python fly_in.py maps/subject_example.txt --visual none
D1-corridorA D2-hub-roof1
D1-tunnelB D2-roof1 D3-corridorA D4-hub-roof1
D1-goal D2-roof2 D3-tunnelB D4-roof1 D5-corridorA
D2-goal D3-goal D4-roof2 D5-tunnelB
D4-goal D5-goal
summary: 5 turns, 5 drones, 4.20 turns per drone on average, 3.40 moves per turn
```

The last line is written to standard error. It reports the total number of
turns and two of the secondary metrics suggested by the subject: the average
turn at which a drone is delivered, and the average number of moves per turn.

The route through `corridorA` (priority) takes 3 turns and the route through
`roof1` (restricted) takes 4. The shortest route lets one drone a turn through
(`tunnelB` holds one drone, and the `hub-corridorA` connection carries one), so
a drone behind the first ones arrives sooner by the longer `roof1` route than
by queuing. D2 and D4 go through `roof1` (see
[detours](#2-next-hops-shortest-and-detours) below), and every drone is
delivered in 5 turns.

### A second example: restricted zones

```text
nb_drones: 6
start_hub: s 0 0
hub: a 1 0 [zone=restricted max_drones=2]
hub: b 1 1 [zone=restricted max_drones=3]
end_hub: g 2 0
connection: s-a [max_link_capacity=2]
connection: a-g
connection: s-b
connection: b-g
```

```text
D1-s-a D2-s-a D3-s-b
D1-a D2-a D3-b D4-s-b D5-s-a
D1-g D3-g D4-b D5-a D6-s-b
D2-g D4-g D6-b
D5-g D6-g
summary: 5 turns, 6 drones, 4.00 turns per drone on average, 3.60 moves per turn
```

`D1-s-a` means that D1 took off toward the restricted zone `a` and is on the
connection `s-a`; it lands in `a` on the next turn (`D1-a`). On turn 2, D5
takes off toward `a` although `a` will be full on turn 3: D1 is scheduled to
leave `a` for `g` on turn 3, which frees the seat D5 lands in (see
[Restricted zones](#5-restricted-zones-reservation-table-and-eviction) below).

## Algorithm and implementation strategy

### Pipeline

```text
map file -> MapParser -> World (Network + nb_drones)
         -> Pathfinder (DistanceMap: Dijkstra from the goal, once)
         -> SimulationEngine: every turn
              Scheduler.decide_moves(state) -> orders
              TurnResolver.resolve(state, orders) -> checked moves
              views: turn log (stdout), terminal / graphical view (stderr / window)
         -> summary (stderr)
```

The scheduler only *decides*; the resolver only *checks and applies* the
rules. They are separate objects, combined by composition in the engine.

### 1. Distance map: Dijkstra from the goal

`DistanceMap` runs one Dijkstra search (with `heapq`) **starting from the end
zone** and walking the connections backwards. Moving into a zone costs that
zone's turn cost (1 for normal and priority, 2 for restricted), so the
distance of a zone is the minimum number of turns a lone drone needs to reach
the goal from there. Blocked zones never get a distance and are never
entered.

Starting from the goal gives the distance of *every* zone in one search,
which is exactly what each drone needs at every turn, wherever it is. It also
detects an unreachable goal: if the start zone has no distance, the program
stops with `error: goal '...' is unreachable from '...'` before simulating.

Capacities are deliberately not part of the distance map: they change every
turn and are handled by the scheduler.

### 2. Next hops: shortest and detours

For each zone, `Pathfinder.next_hops` lists every neighbor `w` such that
`cost(w) + distance(w) == distance(here)`: the moves that keep a drone on a
shortest route. Several entries mean several equally short routes, which is
how the drones are spread over parallel paths.

Priority zones are handled as a **tie-break only**: among equally short next
hops, priority zones come first; otherwise the order is the declaration order
of the connections. A drone never takes a longer route just to pass through a
priority zone.

**Detours**: only a drone that would otherwise wait (none of its shortest next
hops is usable) tries one of `Pathfinder.detour_hops`: every neighbor `w` that
can reach the goal but is not a shortest next hop (`cost(w) + distance(w)` is
longer than the shortest route), including moves sideways or back.
`DetourPolicy` allows one only if

- **no backflow**: the drone has never been in `w` (the policy remembers every
  zone each drone has been in);
- **not slower than waiting**: `cost(w) + distance(w) + queue(w) <=
  distance(here) + ahead(here)`. `ahead(here)` counts the drones in the zones
  the shortest hops from here lead to; `queue(w)` counts the drones in `w` and
  in the zones its shortest hops lead to. Both count landing targets and the
  moves already decided this turn.

In other words, a drone takes a longer but free route only when it is not
slower than queuing on the shortest one; counting the detour's own queue keeps
drones from leaving one crowded route for another.

### 3. Turn scheduling order

Every turn, the scheduler builds the orders in this order:

1. Drones in flight toward a restricted zone get no order: they must land this
   turn, and the engine lands them.
2. Moves planned on earlier turns that are due this turn (evictions, see
   below) are ordered first.
3. The other drones standing in zones are decided **zone by zone**, the zones
   sorted by
   - distance to the goal, closest first;
   - then zones on the priority route first (a priority zone, or a zone with a
     priority zone among its shortest next hops);
   - then zones with fewer exits (shortest hops and detours) first;
   - then declaration order.

Deciding the drones closest to the goal first means that a drone leaving a
zone has already been decided when the drone behind it asks for that zone, so
the room it frees can be used in the same turn. Deciding zones with fewer exits
first keeps a drone that has a choice from taking another zone's only way out.
Drones in the same zone have the same moves, so their order within the zone
does not matter. A drone takes the first of its shortest next hops that has
room; otherwise it tries its allowed detours; otherwise it waits.

### 4. Capacity rules

- A zone's capacity is checked on its **final load** of the turn: drones
  leaving a zone free their room for drones entering it in the same turn
  (chains and rotations are allowed as long as the final load fits).
- A connection's capacity counts the drones **departing** across it during the
  turn, in either direction (a connection is one shared link). A drone landing
  in a restricted zone leaves its connection on that turn, so it does not use
  the connection's capacity on the landing turn.
- The start and end zones have no capacity limit. A drone that reaches the end
  zone is delivered and is no longer tracked.

### 5. Restricted zones: reservation table and eviction

A move into a restricted zone takes two turns, and the drone may not wait on
the connection: it must be able to land on the next turn. So when a drone
takes off at turn `t`, the zone must have a seat at `t+1` **and on every later
turn for which a move is already planned**.

The scheduler keeps a `ReservationTable`: one table of planned moves keyed by
(zone, turn the drone enters it). It holds the landings of the drones in
flight (rebuilt from the state at every turn) and the evictions described
below. A zone's projected load on a future turn is: the drones in it now +
the planned entries up to that turn - the planned departures up to that turn.
A drone without a planned departure is assumed to stay.

If a restricted zone has no seat when a drone wants to take off toward it,
the scheduler tries to **evict** an occupant: it plans that occupant to move
on, on the needed turn, along one of its own shortest next hops. That move
needs room too (the connection on that turn, a seat in the next zone), so if
the next zone is full, one of *its* occupants is evicted the same way,
**recursively**. Every eviction moves a drone strictly closer to the goal, so
the recursion always ends (the end zone always has room). If any step fails,
every move planned during the attempt is **rolled back** and the drone tries
its next option or waits. Planned evictions are ordinary moves: they are
played first on their turn, and a drone with a planned eviction may still move
earlier through an ordinary decision, in which case the plan is dropped.

The same mechanism covers one more case ("rule 6'"): an ordinary move into a
normal or priority zone that has room now, but whose seat is already promised
to a drone planned to enter later. The drone may enter only if an eviction
(possibly of the entering drone itself) can be planned so that the zone is
never over capacity on those later turns.

**Eviction is a last resort.** When a drone chooses where to move, it first
looks at every shortest next hop without evicting anyone. Only if none of them
is usable does it try them again, this time allowing occupants to be evicted
(scheduled to move on) to make room. Otherwise a drone would pile onto the
first listed route by evicting occupants, even when an equally short route was
simply free, which can slow the whole run down. In our tests on 7,832 random
maps, this rule reduced the number of maps that got slower than the scheduler
without evictions from 6 to 1. Allowed detours are tried in the same two steps
(without, then with eviction).

### 6. Safety: an independent check of every turn

`TurnResolver` does not trust the scheduler. Before applying a turn it checks
every order (known, undelivered, not in flight, one order per drone, into an
adjacent non-blocked zone), the connection capacities and the final zone
loads, and it lands every drone in flight. **If a drone in flight cannot land
because its zone is full, the drone would be stuck on its connection, which
the rules forbid: the turn is rejected with an error** (`... is stuck on
connection ...`). Nothing is applied unless the whole turn is legal. The
engine also stops with an error if a turn passes with no drone moving, or if
the run exceeds a generous turn limit (`2 x zones x drones`), so a scheduler
bug can never produce an endless loop or an invalid log.

Every run ends: a shortest move (planned evictions included) strictly lowers
the mover's distance to the goal, and a detour only enters a zone the drone has
never been in, so each drone makes finitely many moves. And at least one drone
moves every turn: planned moves and landings always happen, and otherwise the
drone closest to the goal always has room on its shortest route (the end zone
is unlimited).

### 7. Trade-offs

The scheduler is greedy: each drone takes the best move available this turn.
This is simple, fast and safe, works well when there are several equally short
routes, and uses longer routes when they are not slower than queuing. Its limit
is that every decision rests on a local estimate made during the turn: drones
are not assigned to routes in advance, so on some maps a detouring drone takes
a seat that a later drone on the shortest route needed, and the run gets slower
than without detours (about 2% of 4,871 random maps in our tests, while about
23% get faster and the total number of turns drops by about 5%).

### 8. Complexity, caching and memory

With `V` zones, `E` connections and `D` drones:

- **Parsing**: linear in the size of the file.
- **Distance map**: one Dijkstra with a binary heap, `O((V + E) log V)`,
  computed **once**. The shortest next hops of every zone are also computed
  once and **cached** by the scheduler (`O(V + E)` memory), as are the detour
  hops and, for every zone, the zones its shortest hops lead to
  (`O(V x (V + E))` once, `O(V^2)` memory). The record of the zones each drone
  has been in takes `O(D x V)` memory. Paths are never
  recomputed during the simulation; only the room left in zones and
  connections is evaluated each turn.
- **One turn**: sorting the drones standing in zones is `O(D log D)` (the
  zone ranks are computed once). Each drone tries at most its next hops twice
  (without, then with eviction). A drone that would wait counts the queues by
  scanning the drones' positions once per detour candidate (`O(D)` each) and
  tries its allowed detours the same two ways.
  A seat check looks at the turns from the arrival to the last planned turn
  (`H`, a few turns ahead), so it costs `O(H^2)` table lookups. An eviction
  attempt adds a recursion whose depth is bounded by the distance to the goal,
  and finding an occupant to evict scans the drones' positions (`O(D)`).
  Failed eviction attempts are not memoized.
- **Whole run**: the number of turns grows roughly like `D` divided by the
  throughput of the map (how many drones can reach the goal per turn), so for a
  given map the total time grows roughly like `D^2 log D` in the worst case.
- **Memory**: `O(V + E)` for the map, the distances and the cached hops,
  `O(D)` for the drones and the reservation table, and the turn log of the
  run (one entry per move).

Measured on a 3-lane map with 32 zones (`--visual none`, Python 3.14, a
laptop): 100 drones in 0.2 s, 1,000 drones in 1.0 s, 3,000 drones in 7.5 s.

### Code structure

```text
fly_in.py                  entry point: arguments, exit codes, last-resort error handling
droneflow/
  cli.py, app.py           argument parsing; Application wires the pipeline
  errors.py                FlyInError and its subclasses (one-line messages)
  models/                  Zone, Connection, Network (hand-built adjacency), Drone, World
  parsing/                 MapReader -> LineTokenizer -> rule table (MapFormat) -> MapValidator
  pathfinding/             DistanceMap (Dijkstra), Pathfinder (shortest and detour hops, routes),
                           FlowGraph / ZoneFlowGraph / ConnectionBottleneck / ShortestHopBottleneck
                           (bottleneck analysis by max-flow min-cut; not used by the run)
  simulation/              SimulationEngine, Scheduler, TurnLedger, ReservationTable,
                           Evictor, DetourPolicy, TurnResolver, SimulationState
  output/                  turn log formatter and printer, run summary
  visualization/           Visualizer protocol, terminal view, graphical view, palette
```

Objects are combined by composition and delegation rather than inheritance
(for example the parser delegates to a reader, a tokenizer and a validator,
and the engine composes a scheduler and a resolver). Every view, and the turn
log printer, implements the same three-method `Visualizer` protocol
(`begin`, `render`, `close`), so the engine does not know which views are
attached.

## Visual representation

Both views follow the simulation turn by turn and never change the turn log:
the terminal view writes to standard error, and the graphical view draws in a
window. With `--visual both`, the two are shown together.

### Terminal view (`--visual terminal`, default)

```text
=== Turn 2 | moved 5 | delivered 0/6 ===
moves: D1-a D2-a D3-b D4-s-b D5-s-a
  s S 1/-        a R 2/2+1*     b R 1/3+1      g E 0/-
drones: a[D1 D2] b[D3] s[D6]
in flight: D4 s-b -> b, D5 s-a -> a
```

- A header with the turn number, the number of moves and the number of
  delivered drones, then the moves of the turn.
- A table of every zone: its role or type (`S` start, `E` end, `.` normal,
  `P` priority, `R` restricted, `X` blocked) and its load against its capacity
  (`-` no limit, `+N` drones arriving on the next turn, `*` full). The table
  is laid out in columns to fit the terminal width, so large maps stay compact.
- Where each drone is (`drones:`), and the drones in flight toward a
  restricted zone, with their connection and destination (`in flight:`).
- Zone names are painted with the color given by `color=` in the map
  (24-bit ANSI colors, so colors with similar names stay distinct). Unknown
  colors keep the terminal's default color.
- Colors are disabled when `NO_COLOR` is set to a non-empty value, or when
  standard error is not a terminal (for example when it is redirected to a
  file). All text is ASCII.
- With `--step`, each frame waits for Enter (`-- press Enter for the next turn
  --`). It only waits when standard input is a terminal, so piped runs never
  block.

### Graphical view (`--visual graphical`)

- The map is drawn with its own coordinates, scaled to fit the window, with
  the y axis pointing up (as on graph paper).
- Zones are filled with their `color=`. Restricted zones are squares with a
  red outline, priority zones have a gold ring, the start and end zones a white
  ring, and blocked zones are gray with a cross.
- Under each zone, a bar shows its load against its capacity (green, orange,
  then red when full) with `load/capacity`; the end zone shows how many drones
  have been delivered.
- Connections are drawn thicker when their capacity is larger, labeled `xN`
  when the capacity is above 1, and highlighted while a drone is flying on
  them.
- Drones are dots: white in a zone, cyan in flight (drawn at the middle of
  their connection); the drones that moved this turn have a gold ring, and a
  gold trail shows each move of the turn. Crowded zones show up to 12 dots and
  a `+N` count.
- A status bar shows the turn, the number of moves, delivered drones and
  drones in flight; the bottom line shows the turn's moves in the output
  format.
- **Hovering over a zone** shows a tooltip with its name, role, type, color,
  load and capacity (and drones arriving), and the ids of the drones in it.
- Controls: `Space` pause/resume, `Right` next turn (one turn at a time while
  paused), `Up`/`+` faster, `Down`/`-` slower (the speed keys halve or double
  the delay between 0.05 and 5 seconds), `Esc`/`q` or the window's close button
  quit.
- `--delay SECONDS` sets the time per turn (0 to 60, default 0.5). `--step`
  starts paused, and the right arrow advances one turn.
- After the last turn the window keeps the final frame (`finished - press esc
  to close`) until it is closed. Closing the window early only stops the
  drawing: the simulation still runs to the end and the turn log is complete.

### How the views help

- The turn log alone shows *who* moved; the views show *why the others did
  not*: full zones (`*` or a red bar), busy connections and drones waiting in
  flight make congestion and bottlenecks visible at a glance.
- Restricted moves are easy to follow: the `+N` counts and the `in flight:`
  line (or cyan dots on the connections) show the drones that will land on the
  next turn, and the seats they need.
- `--step` and the pause key make it possible to check a turn against the
  rules by hand, and the zone tooltip gives exact numbers on large maps.
- The colors of the map are kept, so the view matches the map author's
  intent, and the summary line gives the score (total turns) and the secondary
  metrics of every run.

## Testing and quality

- `make lint` and `make lint-strict` pass (`flake8`, `mypy` and
  `mypy --strict`).
- `make test` runs the unit tests in `tests/` (pytest; the graphical tests run
  headless and are skipped when pygame-ce is not installed).
- Beyond the unit tests, the turn logs of many hand-written maps (invalid
  inputs, edge cases, capacity and restricted-zone scenarios) were replayed by
  a separate checker during development, to confirm that no rule is broken on
  any turn; the eviction rules were also checked this way on thousands of
  random maps.

## Resources

### References

- E. W. Dijkstra, "A note on two problems in connexion with graphs",
  *Numerische Mathematik* 1, 1959: the shortest-path algorithm used for the
  distance map.
- Python documentation: [`heapq`](https://docs.python.org/3/library/heapq.html)
  (priority queue), [`argparse`](https://docs.python.org/3/library/argparse.html),
  [`dataclasses`](https://docs.python.org/3/library/dataclasses.html),
  [`typing`](https://docs.python.org/3/library/typing.html),
  [`pdb`](https://docs.python.org/3/library/pdb.html).
- D. Silver, "Cooperative Pathfinding", AIIDE 2005: reservation tables in
  space and time for multi-agent pathfinding (background reading on the
  problem family).
- R. Stern et al., "Multi-Agent Pathfinding: Definitions, Variants, and
  Benchmarks", SoCS 2019: an overview of multi-agent pathfinding problems.
- [pygame-ce documentation](https://pyga.me/docs/).
- [mypy documentation](https://mypy.readthedocs.io/) and
  [flake8 documentation](https://flake8.pycqa.org/).
- [NO_COLOR](https://no-color.org/): the convention for disabling colored
  output.

### How AI was used

AI (Claude by Anthropic, used through Claude Code) was used throughout the
project, under the following division of roles:

- **Subject analysis**: translating the subject into Japanese, listing its
  requirements and pointing out ambiguous points (for example how to read
  "the first line" and how to count connection capacity), which the author
  then decided.
- **Design discussion and review**: discussing designs, comparing
  alternatives, measuring them with throw-away prototypes, and reviewing code
  and test plans. The design decisions are the author's, for example the
  per-turn scheduler order (zone by zone, fewer exits first), treating
  priority zones only as a tie-break, the detour rule (take a longer route when
  it is not slower than waiting, never re-entering a zone), the reservation-table and eviction model for restricted zones,
  and rule 6'. Some were chosen by the author among options the AI proposed
  and measured, such as making eviction a last resort.
- **Implementation and tests**: from the pathfinding stage onward, at the
  author's explicit request, the AI wrote implementation code and unit tests
  in phases (pathfinding, simulation engine, scheduler, visualization, command
  line, reservation table and eviction), each following a design agreed with
  the author, with the tests designed in a separate phase before being written.
  The author reviewed the results.
- **Documentation**: drafting this README.

The record of the decisions (with the alternatives considered), the research
notes and the bug log are kept in the project's development branch, not in this
branch.
