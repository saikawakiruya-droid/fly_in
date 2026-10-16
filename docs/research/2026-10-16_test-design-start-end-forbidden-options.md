# テスト設計: start_hub / end_hub の禁止オプション(`zone=blocked`)

- 日付: 2026-10-16
- フェーズ: **テスト設計**(テストコードはまだ書かない。作成は別フェーズで行う)
- 対象ブランチ: `test/start_end_forbidden_options`(`feature/start_end_forbidden_options` から分岐)
- 対象コード: `droneflow/parsing/map_format.py`(`ForbiddenOption`、`LineSpec.forbidden`、`LineSpec.build` の検査、
  `START_END_FORBIDDEN`、`_zone_spec` の `forbidden` 引数)、`droneflow/parsing/map_validator.py`(`ValueError` → `ParseError` の包み直し。変更なし)
- 参照した決定: `docs/decisions.md`
  - 2026-10-16「start_hub / end_hub に付けてはいけないオプション群を仕様表で宣言し、`ParseError` にする」(本変更)
  - 2026-10-16「start_hub / end_hub が `zone=blocked` のマップは到達不能として扱う」(上記で置き換え。`Pathfinder` の防御は残す)
  - 2026-09-17「start/end の `max_drones` は None に正規化」(維持)
  - 2026-10-04「tokenizer は構文、仕様表は行ごとの変換、`map_rules` は行をまたぐ検査」
  - 2026-10-16「`nb_drones` はファイルの物理的な1行目」
- 参照した課題の条項: VII.3(blocked は進入・通過不可)、VII.4(マップ書式、start/end の `max_drones` は無視)

## 方針

- 新しいテストファイルは作らず、既存の2ファイルに追記する。
  - `tests/parsing/test_map_format.py` — 仕様表の単体レベル(`LineSpec.build` を直接呼ぶ。F01〜F06)
  - `tests/parsing/test_map_parser.py` — `MapParser` 経由の E2E(`tmp_path` にマップを書く既存の `write_map` を使う。M01〜M07)
- マップ文字列は必ず `nb_drones:` を**物理的な1行目**に置く(既存の `MINIMAL_MAP` の形に合わせる)。
- 行番号の確認は既存テストと同じく `excinfo.value.line_number` で行い、文言は `pytest.raises(..., match=...)` または
  `str(excinfo.value)` で確認する(`ParseError` の文字列は `line N: <message>`)。
- 単体レベルで「仕組み」(既定値・キーが書かれた時だけ一致・変換後の値で比較)を確認するため、`DEFAULT_FORMAT` とは別に
  テスト内で小さな `LineSpec` を組み立てる(F04, F05)。`START_END_FORBIDDEN` の中身は増える可能性があるので、
  その仕組みの確認を `zone=blocked` 1件に依存させない。
- `tests/pathfinding/test_pathfinder.py` の P02-d(コード内で組んだ end が blocked のネットワーク)は、
  決定どおり防御として残るのでそのまま維持する(変更しない)。
- `revie_case/` には依存しない。

## ファイル構成

```
tests/
├── README.md                    # 作成フェーズで test_map_format / test_map_parser の説明に禁止オプションを追記する
└── parsing/
    ├── test_map_format.py       # 追記: F01〜F06(import に ForbiddenOption, LineSpec, START_END_FORBIDDEN を追加)
    └── test_map_parser.py       # 追記: M01〜M07
```

## ケース一覧

### 仕様表の単体レベル(`tests/parsing/test_map_format.py`)

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定/条項 |
|---|---|---|---|---|
| F01 | `LineSpec.forbidden` の既定値 | `DEFAULT_FORMAT.find("hub")`、`find("connection")`、`DEFAULT_FORMAT.header`。加えて `forbidden` を渡さずに組んだ `LineSpec` | いずれも `forbidden == ()` | 「既定は空」。hub など start/end 以外の行に禁止が漏れていないこと |
| F02 | `START_END_FORBIDDEN` が start/end の両方に付く | `DEFAULT_FORMAT.find("start_hub")` と `find("end_hub")` | 両方とも `spec.forbidden == START_END_FORBIDDEN`。`ForbiddenOption("zone", ZoneType.BLOCKED) in START_END_FORBIDDEN`。`START_END_FORBIDDEN` に key が `"max_drones"` の要素がない | 「定数1つを両方の行に渡す」宣言の仕組み。片方だけに付け忘れる退行を防ぐ。`max_drones` は禁止に含めない(VII.4) |
| F03 | start/end の `build` が `ValueError` | parametrize: `start_hub` / `end_hub` の spec で `build(["a", "0", "0"], {"zone": "blocked"})` | `ValueError`、文言が `<keyword> cannot have zone=blocked` に一致(`keyword` はそれぞれ `start_hub` / `end_hub`) | 文言の形(`MapValidator` がこれをそのまま `ParseError` に包む) |
| F04 | キーが書かれた時だけ一致する | テスト内で `LineSpec(..., metadata=(FieldSpec("zone", to_zone_type, default=ZoneType.NORMAL),), forbidden=(ForbiddenOption("zone", ZoneType.NORMAL),))` を組む | `build([...], {})` は成功(既定値は禁止値と同じ NORMAL だが、キーが書かれていない)。`build([...], {"zone": "normal"})` は `ValueError` | `option.key in metadata` の条件。既定値で埋まった値まで禁止すると、何も書いていない行が拒否されてしまう |
| F05 | 変換後の値で比べ、文言には生の値を出す | テスト内で `metadata=(FieldSpec("max_drones", to_positive_int, default=1),)`、`forbidden=(ForbiddenOption("max_drones", 5),)` の `LineSpec` を組む | `{"max_drones": "05"}` は `ValueError` で、文言は `max_drones=05`(書かれたとおり)を含む。`{"max_drones": "6"}` は成功 | decisions「比較は変換後の値で行う(値は型付きで書く)」。文字列比較だと `"05"` を見逃す。文言は利用者が書いた値を示す |
| F06 | 変換エラーは禁止の検査より先 | `start_hub` の spec で `build(["s", "0", "0"], {"zone": "blocked", "max_drones": "0"})` | `ValueError`、文言は `max_drones must be a positive integer`(`cannot have` ではない) | 現状の順序(全フィールドを変換してから禁止を検査)を固定する。変換できない値は禁止値と比べられないため、この順序が自然 |

### MapParser 経由(`tests/parsing/test_map_parser.py`)

| ID | 対象 | セットアップ(マップ) | 期待結果 | 意義・守る決定/条項 |
|---|---|---|---|---|
| M01 | blocked な start_hub | `nb_drones: 1` / `start_hub: s 0 0 [zone=blocked]` / `end_hub: e 1 1` | `ParseError`、`line_number == 2`、`str(excinfo.value) == "line 2: start_hub cannot have zone=blocked"` | 本変更の基本形。行番号と文言(decisions のメッセージ例そのもの) |
| M02 | blocked な end_hub(行番号は物理行) | `nb_drones: 1` / `start_hub: s 0 0` / `# comment` / 空行 / `end_hub: e 1 1 [zone=blocked]` | `ParseError`、`line_number == 5`、文言 `end_hub cannot have zone=blocked` | end 側も拒否されること。コメント・空行を挟んでも物理行番号で報告されること |
| M03 | 他のオプションと一緒・順序違い | parametrize(start_hub の行): `[zone=blocked color=red]`、`[color=red zone=blocked]`、`[max_drones=3 color=gray zone=blocked]` | いずれも `ParseError`、`line_number == 2`、文言 `start_hub cannot have zone=blocked` | メタデータの書き順や他キーの有無に左右されないこと。`max_drones` があっても無視されず先に通り、blocked で落ちること |
| M04 | 普通の hub の blocked は引き続き可 | `MINIMAL_MAP + "hub: h 2 2 [zone=blocked]\n"` | 例外なし、`get_zone("h").zone_type is ZoneType.BLOCKED` | 禁止は start/end 限定(VII.3 の blocked ゾーン自体は正当)。サンプルマップの `obstacleX` でも間接的に確認済みだが、意図を明示する |
| M05 | start/end の他のゾーンタイプ・省略は可 | parametrize: キーワード(`start_hub` / `end_hub`)× メタデータ(`[zone=normal]`、`[zone=restricted]`、`[zone=priority]`、なし)。もう一方は素の行 | 例外なし。そのゾーンの `zone_type` が書いた値(なしなら `NORMAL`) | 禁止しすぎていないこと。restricted な end(Stage 3 の D03)など、他のステージが前提にする組み合わせを壊さない |
| M06 | start/end の `max_drones` は引き続き無視 | parametrize(`start_hub` / `end_hub`): `[zone=priority max_drones=5]` | 例外なし、`max_drones is None`、`zone_type is ZoneType.PRIORITY` | decisions 2026-09-17 と VII.4。既存の `test_max_drones_is_normalized_to_none_for_start_and_end` を残したうえで、他の(許される)オプションと組み合わせても None になることを確認する |
| M07 | 以前は経路探索で失敗したマップが、パースで失敗する | `nb_drones: 1` / `start_hub: s 0 0` / `end_hub: g 1 1 [zone=blocked]` / `connection: s-g` | `MapParser.parse()` が `ParseError`(`line_number == 3`)。`UnreachableGoalError` ではない(`Pathfinder` まで進まない) | decisions の方針変更(到達不能扱い → パースで拒否)の退行防止。エラーが入力の行で知らされること |

ケース数: 13(F01〜F06、M01〜M07)。parametrize による展開後は約 25 件。

## 気づいた点(作成フェーズ・ユーザー判断向け)

実装のバグは見つからなかった(`docs/bugs.md` への追記なし)。既存の 153 件のテストはこのブランチで全件通過する。
以下は本変更の範囲外だが、テスト作成時に関係しうる既存の挙動。

1. **同じキーを2回書くと後勝ちになる**: `[zone=blocked zone=normal]` は tokenizer で `zone=normal` だけが残り、
   start_hub でもエラーにならない(逆順 `[zone=normal zone=blocked]` はエラー)。重複キーを拒否しない tokenizer の既存の挙動で、
   禁止オプションに限らず全キーに共通する。本設計ではケースに含めない。重複キーを `ParseError` にするかは別途ユーザー判断。
2. **start/end の `max_drones` は「無視」だが、値の検査は行われる**: `start_hub: s 0 0 [max_drones=0]` は
   `max_drones must be a positive integer` の `ParseError` になる(F06 で順序として固定)。2026-09-17 の決定からの既存の挙動で、
   VII.4 の「無視」を「値も見ない」と読むなら変更の余地がある。現状維持なら追加の対応は不要。
3. `tests/README.md` のカバレッジ欄(`test_map_format.py` / `test_map_parser.py` の説明)に、作成フェーズで
   「start/end の禁止オプション(`zone=blocked`)」を追記する。`2026-10-16_test-design-stage3-pathfinding.md` の
   「パーサー側のケースは別途」という記述は、本設計で対応した。
