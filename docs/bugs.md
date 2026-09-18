# バグ記録(Bug Log)

実装中に発生したバグ・不具合の発生箇所をここに記録していく。
レビュー前後に必ず参照すること。

フォーマット:

```
## YYYY-MM-DD: <症状の見出し>
- 発生箇所: <ファイル>:<行>
- 症状:
- 原因:
- 対応状況: 未対応 / 対応中 / 対応済み(コミット等の参照)
```

---

## 2026-09-17: Drone.current_zone の型ヒントとdocstringの不整合

- 発生箇所: `droneflow/models/drone.py:20`(docstring)/`:32`(型ヒント)
- 症状: docstringには「IN_TRANSIT中はNoneになる」と明記されているのに、
  型ヒントは `current_zone: str`(Optionalでない)になっていた。mypy --strictの下で
  IN_TRANSIT中に `current_zone = None` を代入するコードを書くと型エラーになる。
- 原因: スケルトン作成時にdocstringと型ヒントが同期していなかった。
- 対応状況: 対応済み。型ヒントを `current_zone: str | None` に修正し、docstringと一致させた。

## 2026-09-17: MapParserが通常hubのmax_drones省略時にNoneを返していた

- 発生箇所: `droneflow/parsing/map_parser.py`(`_parse_zone_line`)
- 症状: `hub:` 行で `max_drones=` メタデータを省略した場合、`Zone.max_drones` が `None`
  (無制限)になってしまっていた。
- 原因: `docs/research/2026-09-05_parser-requirements.md` に記載の
  「`max_drones=<number>`(既定値1)」を実装時に見落とし、start/end hub用の
  「省略時はNoneに正規化する」ロジック(`docs/decisions.md` 2026-09-17決定)と混同した。
  通常hubの既定値は1であり、Noneはstart/end hub専用の扱い。
- 対応状況: 対応済み。通常hubで `max_drones` 省略時は `1` を、指定時はその正整数値を使うよう修正。
  start/end hubのみ常に `None` に正規化する既存ロジックはそのまま維持。
