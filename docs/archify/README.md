# archify diagrams

Diagrams made with archify that are worth keeping, in two sets: by folder (structure) and by feature (runtime behavior).
They live under `docs/`, so they are committed to `develop` only and never to `main` (the deliverable).

## Layout

```
docs/archify/
└── <diagram-name>/          # folder-<name> or feature-<name>
    ├── candidate.json        # the diagram source (authoritative)
    └── <diagram-name>.html   # the rendered diagram (open in a browser)
```

- One folder per diagram. Updates overwrite the files in place; git history keeps earlier versions.
- `meta.repository.revision` in `candidate.json` records which commit the diagram describes.
- Check receipts (`*.finalize*.json`, `*.browser-check.json`, `*.delivery.json`, `review-*/`) are ignored by `.gitignore`.

## Diagrams

By folder (`folder-*`: what is where):

| Folder | Type | Shows |
|---|---|---|
| `folder-tree` | tree | Every folder and file of the repository |
| `folder-overview` | architecture | Which folder imports which |
| `folder-top-level` | class | `app.py`, `cli.py`, `errors.py` (exception hierarchy) |
| `folder-models` | class | `models/` |
| `folder-parsing` | class | `parsing/` |
| `folder-interchange` | class | `interchange/` |
| `folder-pathfinding` | class | `pathfinding/` |
| `folder-simulation` | class | `simulation/` (engine side) |
| `folder-scheduling` | class | `simulation/scheduling/` |
| `folder-output` | class | `output/` |
| `folder-visualization` | class | `visualization/` |

By feature (`feature-*`: what happens when it runs):

| Folder | Type | Shows |
|---|---|---|
| `feature-run` | workflow | From `fly_in.py` to the exit code, with the options |
| `feature-parse` | sequence | Reading a map file into a World |
| `feature-pathfinding` | workflow | Distances and next hops |
| `feature-turn` | sequence | One turn: decide, check and apply, notify |
| `feature-decide` | workflow | How the Scheduler decides one turn's moves |
| `feature-drone` | lifecycle | The states of one drone |
| `feature-output` | dataflow | Where each kind of output goes |

## Workflow

1. Draft diagrams in `_tmp/` during a conversation, as before.
2. Move only the ones to keep here (promotion): point `meta.output` in `candidate.json` at
   `docs/archify/<diagram-name>/<diagram-name>.html` and rerun archify `finalize` to rebuild the HTML.
3. Delete the promoted drafts from `_tmp/` as part of the same step.
