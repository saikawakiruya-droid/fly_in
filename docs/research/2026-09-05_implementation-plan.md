# 調査記録: 実装ステージの分解とフローチャート

- 日付: 2026-09-05
- 依頼内容: 「課題において必要な実装の段階を作りフローチャートを作成してください」
- 公開アーティファクト(フローチャート): https://claude.ai/code/artifact/20813f2a-eb57-4bcf-8821-33ea301f335d

依存関係順に11ステージへ分解した。各ステージはGitHub Issueとしても登録している
(マイルストーン: Foundation / Core Pipeline / Visualization & QA / Docs & Bonus)。

## Stage 0 — Setup & Scaffolding
Goal: Prepare a repository that already satisfies the Common Instructions before any domain code exists.
- Everything at the repo root (submission requirement).
- `Makefile`: install, run, debug (pdb), clean, lint, optional lint-strict.
- `.gitignore` for Python artifacts; a virtual environment.
Depends on: —

## Stage 1 — Domain Model (OOP)
Goal: Define the typed vocabulary every later stage is built on.
- `Zone` (name, x, y, type, color, max_drones), `Connection` (zone pair, max_link_capacity).
- `Network` holding the hand-built adjacency — no networkx/graphlib.
- `Drone`, and a zone-type enum carrying each type's turn cost.
Depends on: Stage 0

## Stage 2 — Parser & Validation
Goal: Turn a map file into Domain Model objects, enforcing every rule in the Parser Constraints section.
- Exactly one start_hub/end_hub; unique names; no dashes or spaces in names.
- No duplicate connections (a-b == b-a); only known zone types.
- `max_drones` on start/end is ignored, not an error.
- Any other problem stops the run with a line number + cause.
Depends on: Stage 1

## Stage 3 — Pathfinding
Goal: Compute movement-cost-aware routes without any graph library.
- Hand-rolled weighted search (Dijkstra/BFS-style) over the adjacency built in Stage 1.
- Edge weight = destination cost: normal/priority = 1, restricted = 2, blocked excluded.
- Prefer priority zones on ties; return multiple candidate paths per drone for later load-balancing.
Depends on: Stage 2

## Stage 4 — Simulation Engine
Goal: Advance the world one discrete turn at a time, enforcing occupancy and movement rules.
- Per-turn zone occupancy and connection-usage counters; outgoing drones free space before incoming drones claim it.
- Restricted-zone transit: once entered, a drone must arrive next turn — no waiting mid-connection.
- Start/end zones exempt from max_drones.
Depends on: Stage 1, Stage 3

## Stage 5 — Multi-Drone Scheduler
Goal: The actual optimization problem: decide, turn by turn, who moves where.
- Distribute drones across disjoint or overlapping paths to maximize simultaneous throughput.
- Resolve zone/link capacity conflicts and deadlocks (two drones each waiting on the other).
- Choose strategic waits when no legal move reduces the total turn count.
Depends on: Stage 3, Stage 4

## Stage 6 — Output Formatter
Goal: Emit the exact turn log the subject requires.
- One line per turn; drones that didn't move are omitted; delivered drones stop being tracked.
Depends on: Stage 5

## Stage 7 — Visualization
Goal: Give the simulation visible feedback — terminal colors and/or a graphical view.
- A static scaffold can start right after Stage 2, since declared color= metadata is already known.
- Live per-turn rendering (drone positions, zone fill levels) hooks up once Stage 6 exists.
Depends on: Stage 2 (early scaffold), Stage 6 (live data)

## Stage 8 — Validation & Testing
Goal: Prove rule compliance, not just that it runs.
- Run every provided map (easy / medium / hard / challenger).
- Author edge-case maps: malformed metadata, duplicate connections, missing start/end, zero capacity.
- Check for zero rule violations turn-by-turn, not only at the final state.
Depends on: Stage 6, Stage 7

## Stage 9 — Documentation
Goal: Satisfy the Readme Requirements chapter and this project's own logging rules.
- README.md: italic 42-attribution line, Description, Instructions, Resources (+ AI-usage disclosure), algorithm rationale, visualization notes, example input/output.
- Reconcile docs/decisions.md and docs/bugs.md against what actually got built.
Depends on: Stage 8

## Stage 10 — Performance & Bonus (optional)
Goal: Push turn counts toward — or under — the benchmark targets.
- Targets: Easy <10 turns, Medium 10–30, Hard <60 turns.
- Bonus graded only once every mandatory item is complete: match/beat every target, optionally beat the Challenger map's 45-turn reference record.
Depends on: Stage 8

## Continuous (not a stage, applies throughout)
- Type safety: `flake8` + `mypy --strict` from Stage 1 onward.
- `docs/decisions.md` / `docs/bugs.md` kept up to date, checked at every review.
