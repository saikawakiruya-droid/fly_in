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
