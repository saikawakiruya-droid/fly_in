# archify diagrams

Diagrams made with archify (the overall picture, per-stage structure, and so on) that are worth keeping.
They live under `docs/`, so they are committed to `develop` only and never to `main` (the deliverable).

## Layout

```
docs/archify/
└── <diagram-name>/          # e.g. overview, stage1-models, stage5-scheduler
    ├── candidate.json        # the diagram source (authoritative)
    └── <diagram-name>.html   # the rendered diagram (open in a browser)
```

- One folder per diagram. Updates overwrite the files in place; git history keeps earlier versions.
- `meta.repository.revision` in `candidate.json` records which commit the diagram describes.
- Check receipts (`*.finalize*.json`, `*.browser-check.json`, `*.delivery.json`, `review-*/`) are ignored by `.gitignore`.

## Workflow

1. Draft diagrams in `_tmp/` during a conversation, as before.
2. Move only the ones to keep here (promotion): point `meta.output` in `candidate.json` at
   `docs/archify/<diagram-name>/<diagram-name>.html` and rerun archify `finalize` to rebuild the HTML.
3. Delete the promoted drafts from `_tmp/` as part of the same step.
