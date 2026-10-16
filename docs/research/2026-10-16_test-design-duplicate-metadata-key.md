# テスト設計: メタデータの重複キーを `ParseError` にする

- 日付: 2026-10-16
- フェーズ: **テスト設計**(テストコードはまだ書かない。作成は別フェーズで行う)
- 対象ブランチ: `test/duplicate_metadata_key`(`fix/duplicate_metadata_key` から分岐)
- 対象コード: `droneflow/parsing/line_tokenizer.py`(`LineTokenizer._split_metadata`。コミット 62388bd)
  - 検査順: エントリごとに「不正なエントリ(`malformed metadata entry`)」→「重複キー(`duplicate metadata key '<key>'`)」。
    未知キー(`unknown metadata key(s)`)の検査はブロック全体を読んだ後の `_split` で行う。
- 参照した決定・記録:
  - `docs/decisions.md` 2026-10-16「メタデータの重複キーは `ParseError` にし、start/end の `max_drones` は無視しつつ値は検査する」
  - `docs/decisions.md` 2026-10-04「tokenizer は構文、仕様表は行ごとの変換、`map_rules` は行をまたぐ検査」
  - `docs/decisions.md` 2026-10-16「`nb_drones` はファイルの物理的な1行目」
  - `docs/bugs.md` 2026-10-16「メタデータの重複キーが後勝ちになり、start/end の `zone=blocked` 検査をすり抜ける」
  - `docs/research/2026-10-16_test-design-start-end-forbidden-options.md`(気づいた点1)

## 方針

- 新しいテストファイルは作らず、既存の2ファイルに追記する。
  - `tests/parsing/test_line_tokenizer.py` — tokenizer 単体(既存の `TOKENIZER` と `line()` を使う。T01〜T04)
  - `tests/parsing/test_map_parser.py` — `MapParser` 経由(既存の `write_map` を使う。M01〜M03)
- 文言は `str(excinfo.value)` の完全一致(`line N: duplicate metadata key 'zone'`)で確認する。キー名は `repr` なので引用符付き。
- `MapParser` 経由のマップは `nb_drones:` を**物理的な1行目**に置く。
- 既存の `test_syntax_errors_carry_the_line_number` の parametrize には混ぜない(文言まで確認したいため、専用のテストにする)。
- `revie_case/` には依存しない。

## ケース一覧

### tokenizer 単体(`tests/parsing/test_line_tokenizer.py`)

| ID | 対象 | 入力(`line(text, number=7)`) | 期待結果 | 意義 |
|---|---|---|---|---|
| T01 | 全行種で重複キーを拒否 | parametrize: `hub: h 1 1 [zone=normal zone=priority]` / `start_hub: s 0 0 [color=red color=blue]` / `end_hub: e 1 1 [max_drones=2 max_drones=3]` / `connection: a-b [max_link_capacity=1 max_link_capacity=2]` | `ParseError`、`line_number == 7`、文言 `line 7: duplicate metadata key '<key>'`(key はそれぞれ `zone` / `color` / `max_drones` / `max_link_capacity`) | 全キー・全行種に共通の構文規則であること(decisions 2026-10-16 理由1) |
| T02 | 同じ値の重複も拒否 | `hub: h 1 1 [zone=normal zone=normal]`、および間に別キーを挟む `hub: h 1 1 [zone=normal color=red zone=normal]` | どちらも `duplicate metadata key 'zone'` | 値が同じでも「書き誤り」として扱う。隣接していなくても検出する |
| T03 | 不正なエントリとの優先順位(トークン順で先に出た問題を報告) | parametrize: (a) `hub: h 1 1 [zone=a zone=]` → `malformed metadata entry: 'zone='` / (b) `hub: h 1 1 [color= zone=a zone=b]` → `malformed metadata entry: 'color='` / (c) `hub: h 1 1 [zone=a zone=b color=]` → `duplicate metadata key 'zone'` | 各期待文言の `ParseError` | 2つ目が不正な形なら重複より不正を報告(a)。同一エントリ内では不正の検査が先、エントリ間では左から順、という現状の順序を固定する |
| T04 | 未知キーとの優先順位 | parametrize: (a) `hub: h 1 1 [colr=x colr=y]` / (b) `hub: h 1 1 [colr=x zone=a zone=b]` / 対照 (c) `hub: h 1 1 [zone=a Zone=b]` | (a) `duplicate metadata key 'colr'`、(b) `duplicate metadata key 'zone'`、(c) `unknown metadata key(s): Zone` | 重複はブロックを読む途中、未知キーは読み終えた後の検査なので重複が先。キーは大文字小文字を区別する(c は重複ではない) |

### MapParser 経由(`tests/parsing/test_map_parser.py`)

| ID | 対象 | セットアップ(マップ) | 期待結果 | 意義 |
|---|---|---|---|---|
| M01 | 退行: blocked を後ろの値で隠せない(両方の順序) | parametrize: `nb_drones: 1` / `start_hub: s 0 0 [<meta>]` / `end_hub: e 1 1`、`<meta>` は `zone=blocked zone=normal` と `zone=normal zone=blocked` | どちらも `ParseError`、`line_number == 2`、文言 `line 2: duplicate metadata key 'zone'`(`start_hub cannot have zone=blocked` ではない) | bugs.md の症状そのもの。修正前は前者が通過し後者だけ失敗していた。順序に関係なく同じ文言になること |
| M02 | 退行: end_hub 側・物理行番号 | `nb_drones: 1` / `# comment` / `start_hub: s 0 0` / 空行 / `end_hub: e 1 1 [zone=blocked zone=normal]` | `ParseError`、`line_number == 5`、文言 `line 5: duplicate metadata key 'zone'` | end 側も同様に拒否。コメント・空行を挟んでも物理行番号(1行目が `nb_drones`)で報告される |
| M03 | 重複なしの通常マップは影響を受けない | `MINIMAL_MAP + "hub: h 2 2 [zone=priority color=red max_drones=2]\nconnection: s-h [max_link_capacity=3]\n"` | 例外なし。`h` の `zone_type is PRIORITY`、`max_drones == 2`、接続の容量 3 | 修正が正常な複数キーのブロックを壊していないこと(全キーを1回ずつ書いた行) |

ケース数: 7(T01〜T04、M01〜M03)。parametrize 展開後は約 15 件。

## 気づいた点(作成フェーズ・ユーザー判断向け)

実装のバグは見つからなかった(`docs/bugs.md` への追記なし)。既存の 183 件のテストはこのブランチで全件通過する。
設計時に上記の各入力を実際に tokenizer に通し、期待結果の文言と一致することを確認済み。

1. **未知キーを重複させると「重複」と報告される**(T04 (a)): `[colr=x colr=y]` は `unknown` ではなく `duplicate metadata key 'colr'`。
   どちらも行番号付きのエラーで評価上の問題はないが、利用者にとっては「キー名の綴り違い」の方が根本原因。
   現状の順序(決定どおり tokenizer の構文段階で検出)を T04 で固定する案とした。変えるなら作成前にユーザー判断。
   - **作成フェーズでの扱い(2026-10-16)**: 現状の優先順位(未知キーより重複を先に報告)をそのまま受け入れ、T04 で固定した。
2. **`nb_drones` 行にもメタデータの重複検査が効く**: `nb_drones: 1 [a=1 a=2]` は `duplicate metadata key 'a'`(未知キーより先)。
   ヘッダーにメタデータを書くケースは稀なので本設計ではケースに含めない。
3. **作成フェーズで `tests/README.md` のカバレッジ欄**(`test_line_tokenizer.py` / `test_map_parser.py`)に「メタデータの重複キー」を追記する。
   `docs/bugs.md` の該当エントリの「単体テストは別途テスト用エージェントが追加する」も、作成後に更新する。
