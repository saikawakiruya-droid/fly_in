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

## 2026-10-16: 1行目がコメントのマップ(配布マップ10枚すべて)を `nb_drones` 欠落として拒否する

- 発生箇所: `droneflow/parsing/map_parser.py`(`parse` の `src.number == 1` 分岐)/
  `droneflow/parsing/line_tokenizer.py`(`tokenize_header`)
- 症状: `# Easy Level 1: ...` のように1行目がコメントのマップで
  `line 1: the first line must be 'nb_drones: <n>'` の `ParseError` になる。配布マップ10枚すべてが該当。
- 原因: 「1行目」を物理的な1行目と扱っているため。
- 対応状況: **バグではなく仕様**(対応不要)。「ファイルの物理的な1行目が `nb_drones:` でなければエラー」を
  正式な方針とした(decisions.md 2026-10-16)。`revie_case/maps/parse_error/E35_comment_first_line.txt` で確認する。

## 2026-10-16: 空ファイルのエラーメッセージの行番号が `line 0` になる

- 発生箇所: 空ファイル時の `ParseError`(`MapParser.parse` 周辺。`revie_case/maps/parse_error/E32_empty_file.txt` で再現)
- 症状: `line 0: map file is empty, ...` と表示される。行番号は1始まりなので `0` は利用者に分かりにくい。
- 原因: 未調査(空ファイル用に行番号0を渡している)。
- 対応状況: 未対応(軽微。メッセージ自体は明確なので評価上の影響は小さい)。

## 2026-10-16: メタデータの重複キーが後勝ちになり、start/end の `zone=blocked` 検査をすり抜ける

- 発生箇所: `droneflow/parsing/line_tokenizer.py:93`(`LineTokenizer._split_metadata` のキー登録部分。修正前は `metadata[key] = value` で上書き)
- 症状: `start_hub: s 0 0 [zone=blocked zone=normal]` のように同じ行で同じキーを2回書くと、後ろの値だけが残り
  エラーにならない。start/end の禁止オプション(`zone=blocked`)の検査を、後ろに `zone=normal` を足すだけで回避できた
  (逆順 `[zone=normal zone=blocked]` はエラーになる)。`[max_link_capacity=1 max_link_capacity=2]` なども黙って後勝ちになる。
- 原因: メタデータを dict に詰める際に、既に同じキーがあるかを確認していなかった。
- 対応状況: 対応済み(`fix/duplicate_metadata_key`、コミット 62388bd)。tokenizer(構文段階)で重複キーを検出し、
  `line N: duplicate metadata key 'zone'` の `ParseError` にする(decisions.md 2026-10-16「メタデータの重複キーは `ParseError` にし…」)。
  単体テスト追加済み(`test/duplicate_metadata_key`): `tests/parsing/test_line_tokenizer.py` の T01〜T04、
  `tests/parsing/test_map_parser.py` の M01〜M03(docstring は「Duplicate key M0x」)。設計は
  `docs/research/2026-10-16_test-design-duplicate-metadata-key.md`。
