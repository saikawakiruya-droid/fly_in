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

## 2026-10-04: MapParserが `hub` のようなコロンなしのキーワードだけの行で例外を起こしていた

- 発生箇所: 分割前の `droneflow/parsing/map_parser.py`(`_parse_line` → `_parse_zone_line`)
- 症状: `hub` とだけ書かれた行で、`ParseError` ではなく `ValueError`(`line.split(":", 1)` の
  アンパック失敗)が送出され、行番号つきのエラーにならなかった。
- 原因: キーワード判定が `line.split(":", 1)[0]` だけで、コロンの有無を確認していなかった。
- 対応状況: 対応済み。分割後の `LineTokenizer.tokenize` はコロンの有無を `partition` で確認し、
  無ければ `unrecognized line` の `ParseError` にする(`tests/parsing/test_map_parser.py` に追加)。

## 2026-10-04: 分割中の `UniqueConnection` が自己ループを重複と誤判定していた

- 発生箇所: `droneflow/parsing/map_rules.py`(`UniqueConnection.check`)。コミット前の実装中に発見。
- 症状: すでに `a-b` がある状態で `a-a`(自己ループ)を宣言すると、重複として拒否された。
- 原因: 重複判定に `existing.involves(zone_b)` を使い、`zone_a == zone_b` のとき
  `zone_a` に接する任意の接続が当てはまってしまった。
- 対応状況: 対応済み。`existing.other_end(zone_a) == zone_b` で判定するよう変更。
  `tests/parsing/test_map_rules.py` に再発防止テストあり。
