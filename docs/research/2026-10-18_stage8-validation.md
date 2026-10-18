# 調査記録: Stage 8(Validation & Testing)の検証結果

- 日付: 2026-10-18
- ブランチ: `test/stage8_validation`(`test/cli_app_makefile` から作成)
- 対象: `revie_case/maps/` の自作マップ63枚、配布マップ10枚(1行目のコメントを除いた写しと、元のまま)、
  `maps/subject_example.txt`
- `droneflow/`・`fly_in.py`・`tests/` は変更していない。`revie_case/` も変更していない(期待結果の更新案は末尾に列挙)

## 方法

1. 各マップで `.venv` の python から `fly_in.py <map> --visual none` を実行し、stdout・stderr・終了コードを保存した。
2. 終了コード0の実行は、ターンログをマップに対して1ターンずつ再生して検査した。検査は使い捨てのスクリプト
   (scratchpad に置いた。リポジトリには入れていない。decisions.md 2026-10-16「出力の検証スクリプトは今は作らない」)で、
   マップの読み込みも `droneflow` を使わずに独立に書いた。検査した項目:
   - 形式: 1行=1ターン、空行なし、各項目が `D<ID>-<zone>` か `D<ID>-<connection>`、ID は 1〜nb_drones、同じ行に同じドローンが2度出ない
   - 移動先が今いるゾーンと接続されている(自己ループでのその場の移動も違反とする)、blocked に入らない
   - restricted へは接続名(`D<n>-a-r`)で出発し、次のターンに必ず `D<n>-r` で到着する(1ターンで restricted に入るのも違反)
   - ゾーン容量: 各ターンの終わりにいる数 ≤ `max_drones`(start / end は除く)。加えて「いる数+到着待ち(予約)」≤ `max_drones`
     (decisions.md 2026-10-16 の予約の規則)
   - 接続容量: そのターンに接続を使う数(通過・restricted への出発・到着、向きは区別しない)≤ `max_link_capacity`
     (2026-10-18 の規則変更後は到着を数えない。末尾の追記を参照)
   - 配達済みのドローンが再び出ない、最後に全機が配達済み、stderr の `summary:` のターン数・機数がログと一致
3. 検査スクリプト自体の確認として、違反を仕込んだログ(ゾーン容量超過、接続容量超過、1ターンで restricted へ、
   飛行中の未到着、空行、非隣接の移動、配達済みの再登場、未配達、blocked への移動、小文字の `d1`)を与え、すべて検出することを確かめた。
4. `--visual` の4モード(none / terminal / graphical / both)を5枚のマップで実行し、stdout がバイト単位で同じことを確かめた。
   graphical は `SDL_VIDEODRIVER=dummy` で、最後のフレームの待ち(`hold_final`)と各ターンの待ちをすぐ返すようにした
   ラッパー経由で `fly_in.main` を呼んだ(`--delay 0`)。
5. 課題 III.2 の lint(`flake8 .`、`mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports
   --disallow-untyped-defs --check-untyped-defs`)、`mypy . --strict`、`pytest tests -q` を実行した。

実行環境: Windows 11、Python 3.14.6、`.venv`。どのマップも実行時間は1秒未満(X07 の10万機で約0.8秒)。

## 結果

判定の凡例: **一致**=期待どおり / **期待が古い**=その後の決定で期待結果が変わった / **問題**=実装の不具合

### parse_ok(5枚)

| マップ | 期待 | 結果 | 判定 |
|---|---|---|---|
| P01_subject_example | 受理 | 終了コード0、7ターン、違反なし | 一致 |
| P02_defaults | 受理(既定値) | 0、4ターン(`mid` に1機ずつ。既定 `max_drones=1`・接続容量1と整合)、違反なし | 一致 |
| P04_metadata_variants | 受理 | 0、6ターン、違反なし | 一致 |
| P05_start_end_max_drones_ignored | 受理、start/end は無制限 | 0、2ターン(4機が同時に出発・同時に到着)、違反なし | 一致 |
| P06_allowed_oddities | 受理(座標重複・自己ループ・`_` と数字の名前) | 0、3ターン(自己ループ `zone_A1-zone_A1` は使わない)、違反なし | 一致 |

### parse_error(35枚)

35枚すべて終了コード1、stderr は `error: line N: ...` の1行のみ(トレースバックなし)。

| マップ | 期待する行 | 結果(stderr) | 判定 |
|---|---|---|---|
| E01_missing_nb_drones | 1 | `line 1: the first line must be 'nb_drones: <n>'` | 一致 |
| E02_nb_drones_after_zone | 1 | `line 1: the first line must be ...` | 一致 |
| E03_nb_drones_zero | 1 | `line 1: n must be a positive integer, got 0` | 一致 |
| E04_nb_drones_negative | 1 | `line 1: n must be a positive integer, got -3` | 一致 |
| E05_nb_drones_not_integer | 1 | `line 1: n must be an integer, got '2.5'` | 一致 |
| E06_nb_drones_missing_value | 1 | `line 1: expected 'nb_drones: <n>', got 'nb_drones:'` | 一致 |
| E07_invalid_zone_type | 3 | `line 3: zone must be one of normal, blocked, restricted, priority, got 'fast'` | 一致 |
| E08_missing_start_hub | 4 | `line 4: missing start_hub` | 一致 |
| E09_missing_end_hub | 4 | `line 4: missing end_hub` | 一致 |
| E10_two_start_hubs | 3 | `line 3: duplicate start_hub` | 一致 |
| E11_two_end_hubs | 4 | `line 4: duplicate end_hub` | 一致 |
| E12_max_drones_zero | 3 | `line 3: max_drones must be a positive integer, got 0` | 一致 |
| E13_max_drones_negative | 3 | `line 3: max_drones must be a positive integer, got -2` | 一致 |
| E14_max_drones_not_integer | 3 | `line 3: max_drones must be an integer, got 'two'` | 一致 |
| E15_link_capacity_zero | 4 | `line 4: max_link_capacity must be a positive integer, got 0` | 一致 |
| E16_link_capacity_float | 4 | `line 4: max_link_capacity must be an integer, got '1.5'` | 一致 |
| E17_duplicate_zone_name | 4 | `line 4: duplicate zone name: a` | 一致 |
| E18_duplicate_connection_same_order | 5 | `line 5: duplicate connection: s-g` | 一致 |
| E19_duplicate_connection_reversed | 5 | `line 5: duplicate connection: g-s` | 一致 |
| E20_connection_unknown_zone | 4 | `line 4: unknown zone: ghost` | 一致 |
| E21_connection_before_zone | 3 | `line 3: unknown zone: g` | 一致 |
| E22_zone_name_with_dash | 3 | `line 3: name must not contain '-', got 'bad-name'` | 一致 |
| E23_coordinate_not_integer | 3 | `line 3: x must be an integer, got '1.5'` | 一致 |
| E24_missing_coordinate | 3 | `line 3: expected 'hub: <name> <x> <y>', got 'hub: a 1'` | 一致 |
| E25_metadata_unclosed_bracket | 3 | `line 3: malformed metadata block` | 一致 |
| E26_metadata_not_key_value | 3 | `line 3: malformed metadata entry: 'restricted'` | 一致 |
| E27_unknown_metadata_key | 3 | `line 3: unknown metadata key(s): speed` | 一致 |
| E28_link_metadata_on_zone | 3 | `line 3: unknown metadata key(s): max_link_capacity` | 一致 |
| E29_unknown_keyword | 3 | `line 3: unrecognized line: 'tunnel: t 1 0'` | 一致 |
| E30_keyword_without_colon | 3 | `line 3: unrecognized line: 'hub'` | 一致 |
| E31_connection_malformed | 4 | `line 4: expected 'connection: <name1>-<name2>', got 'connection: s g'` | 一致 |
| E32_empty_file | 1 または空と分かるメッセージ | `line 0: map file is empty, expected 'nb_drones: <n>' as the first line` | 一致(メッセージで空と分かる。`line 0` は既知の軽微なバグ、bugs.md 2026-10-16・未対応) |
| E33_comments_only | `nb_drones` がない旨 | `line 1: the first line must be 'nb_drones: <n>'` | 一致 |
| E34_trailing_garbage | 3 | `line 3: malformed metadata block` | 一致 |
| E35_comment_first_line | 1 | `line 1: the first line must be 'nb_drones: <n>'` | 一致(decisions.md 2026-10-16「`nb_drones` は物理的な1行目に限る」) |

### sim(12枚)

| マップ | 期待 | 結果 | 判定 |
|---|---|---|---|
| S01_single_drone_linear | 3ターン `D1-a`/`D1-b`/`D1-g` | 同じ | 一致 |
| S02_zone_capacity_default | 4ターン、`a` に2機いない | 4ターン(期待どおりのパイプライン) | 一致 |
| S03_zone_capacity_two | 3ターン、`m` は最大2機 | 3ターン | 一致 |
| S04_link_capacity_bottleneck | 4ターン、同じ接続を2機が通らない | 4ターン | 一致 |
| S05_link_capacity_wide | 1ターン `D1-g D2-g D3-g` | 同じ | 一致 |
| S06_restricted_transit | `D1-s-r`/`D1-r`/`D1-g` | 同じ | 一致 |
| S07_restricted_no_wait_on_link | 出発の次に必ず到着、最適4ターン | 5ターン: `D1-s-r` / `D1-r` / `D1-g D2-s-r` / `D2-r` / `D2-g`。出発の次は必ず到着 | **期待が古い**(下記) |
| S08_priority_preferred | 2ターン、`p` 経由 | `D1-p`/`D1-g` | 一致 |
| S09_restricted_vs_detour | 3ターン | 3ターン(restricted の近道を使用) | 一致 |
| S10_blocked_avoided | `x` が出ない、4ターン | 4ターン、`x` なし | 一致 |
| S11_split_two_paths | 3ターン | 3ターン(`a` と `b` に分散) | 一致 |
| S12_link_narrower_than_zone | 3ターン、`a→g` は1ターン1機 | 3ターン、期待どおり | 一致 |

S07 について: 4ターンにするには、2ターン目に D1 の到着(`D1-r`)と D2 の出発(`D2-s-r`)が同時に起きる必要がある。
decisions.md 2026-10-16「restricted への移動は、出発時に到着先の容量を予約し…」の 3(飛行中のドローンは到着するターンも
接続を使う)により `s-r`(容量1)は2ターン目に D1 が使っており、同じく 1(出発時に `r` の容量を予約)により `r`(容量1)も
D1 で埋まっている。この規則の下では5ターンが最適で、結果は正しい。マップのコメント「Expected best: 4 turns (D2 takes off
as D1 lands, ...)」と README.ja.md の「最適4ターン」は、この決定より前に書かれたもの。

### edge(11枚)

| マップ | 期待 | 結果 | 判定 |
|---|---|---|---|
| X01_single_drone_start_to_end | 1ターン `D1-g` | 同じ | 一致 |
| X02_disconnected_goal | パース成功→明確な到達不能エラー | 終了コード1、`error: goal 'g' is unreachable from 's'` | 一致 |
| X03_only_path_blocked | X02 と同じ | 同上 | 一致 |
| X04_isolated_zone_but_solvable | 3ターン | 3ターン | 一致 |
| X05_no_connections | X02 と同じ | 同上 | 一致 |
| X06_huge_capacity | 1ターンで50機 | 1ターン、50機 | 一致 |
| X07_huge_nb_drones | 1ターン、現実的な時間 | 1ターン、10万機、約0.8秒 | 一致 |
| X08_many_drones_narrow | 201ターン、デッドロックなし | 201ターン | 一致 |
| X09_dead_end_branch | 4ターン、`d1`〜`d3` に入らない | 4ターン、入らない | 一致 |
| X10_cycle | 5ターン、`c3`・`c4` に入らない | 5ターン、`c1`→`c2` のみ | 一致 |
| X11_large_grid | 数秒以内、正しい出力 | 74ターン、約0.1秒、違反なし | 一致 |

### 配布マップ(10枚)と課題の例

1行目のコメントを除いた写し(`nb_drones:` を物理的な1行目にしたもの。コメント・空行を除けば元と同じ内容であることを確認)で実行した。

| マップ | 機数 | 結果(ターン) | 目標(VII.7) | 判定 |
|---|---|---|---|---|
| easy/01_linear_path | 2 | 4 | ≤ 6 | 目標内 |
| easy/02_simple_fork | 4 | 4 | ≤ 8 | 目標内 |
| easy/03_basic_capacity | 4 | 4 | ≤ 6 | 目標内 |
| medium/01_dead_end_trap | 5 | 8 | ≤ 12 | 目標内 |
| medium/02_circular_loop | 6 | 15 | ≤ 15 | 目標内(ちょうど) |
| medium/03_priority_puzzle | 5 | 8 | ≤ 12 | 目標内 |
| hard/01_maze_nightmare | 8 | 13 | ≤ 30 | 目標内 |
| hard/02_capacity_hell | 12 | 16 | ≤ 35 | 目標内 |
| hard/03_ultimate_challenge | 15 | 26 | ≤ 45 | 目標内 |
| challenger/01_the_impossible_dream | 25 | 43 | < 45(基準記録) | 基準記録を更新 |
| maps/subject_example.txt | 5 | 7 | — | 一致(P01 と同じ出力) |

カテゴリ平均: easy 4.0(< 10)、medium 10.3(10〜30)、hard 18.3(< 60)。すべて違反なし。

元の配布マップ(1行目がコメント)10枚は、どれも `error: line 1: the first line must be 'nb_drones: <n>'`・終了コード1
(decisions.md 2026-10-16 / 2026-10-18「入力ファイルの制約は README に書き、配布マップには触れない」どおり)。

### 集計

| カテゴリ | 枚数 | 一致 | 期待が古い | 問題 |
|---|---|---|---|---|
| parse_ok | 5 | 5 | 0 | 0 |
| parse_error | 35 | 35 | 0 | 0 |
| sim | 12 | 11 | 1(S07) | 0 |
| edge | 11 | 11 | 0 | 0 |
| 配布マップ(写し)+課題の例 | 11 | 11(全て目標内) | 0 | 0 |
| 配布マップ(元のまま) | 10 | 10(方針どおりの line 1 エラー) | 0 | 0 |

## チェックリスト(revie_case/README.ja.md「どの出力にも使えるチェックリスト」)の結果

終了コード0だった36回の実行(parse_ok 5、sim 12、edge 8、配布マップ写し 10、課題の例 1)すべてで、項目1〜9の違反は0件。
予約を含めたゾーン容量(いる数+到着待ち ≤ `max_drones`)と、stderr の `summary:` とログの一致も、すべて問題なし。

## 可視化モード・lint・テスト

- `--visual` の4モード: 課題の例、hard/03、challenger、S07、P04 の5枚で、none / terminal / graphical / both の stdout がバイト単位で同一。
  `--visual none` の本実行の stdout とも同一。graphical / both はターンごとに1回待ち(ラッパーで即時に返した)、最後に1回 `hold_final` の待ちを呼んだ。
- `flake8 .`: 指摘なし。
- `mypy .`(課題 III.2 のフラグ): `Success: no issues found in 70 source files`。
- `mypy . --strict`: 同上。
- `pytest tests -q`: 505 passed。

## 見つかった問題

ルール違反・異常終了・トレースバックは見つからなかった。新しくバグとして `docs/bugs.md` に記録したものはない。

気づいた点(軽微。バグとしては記録していない。扱いはユーザー判断):

1. `summary:` 行が単数でも複数形になる(例: `summary: 1 turns, 1 drones, ...`)。表示だけの問題。
2. 既知の未対応: E32 の `line 0`(bugs.md 2026-10-16)。
3. 評価シートのライブコーディング(`--capacity-info`)は未実装(評価の場で追加する想定の項目なので、Stage 8 の対象外)。
4. `revie_case/` には、その後の決定で加わった規則を確かめるマップがない: start/end の `zone=blocked`(ParseError)、
   メタデータの重複キー(ParseError)。単体テストでは確認済みだが、レビュー用の入力として足すかはユーザー判断。

## revie_case/README.ja.md などで古くなった期待結果(更新はユーザーが行う)

1. `revie_case/README.ja.md` の sim 表 S07「最適4ターン」→ 現在の規則では5ターンが最適(上記)。
   同じ記述が `revie_case/maps/sim/S07_restricted_no_wait_on_link.txt` の5行目のコメント
   「Expected best: 4 turns (D2 takes off as D1 lands, lands as D1 leaves).」にもある。
2. `revie_case/README.ja.md` の「現状の実行結果(2026-10-16、`feature/split_map_parser` 5d48823)」の節:
   「シミュレーション部はまだ未実装のため、sim / edge はパースのみ確認」「sim / edge: 全マップ受理」は古い。
   現在はシミュレーションまで実行でき、X02 / X03 / X05 はパース後に `goal 'g' is unreachable from 's'` で終了する(期待表どおり)。
   本記録の結果に置き換えるとよい。
3. (revie_case 外)`docs/research/2026-10-16_review-test-patterns.md` の「1行目コメントの扱いを P03 だけで試すため」:
   P03 は現在なく、1行目コメントの確認は E35 で行う。

## 追記(2026-10-18): restricted の到着ターンを接続容量に数えない規則への変更後

`docs/decisions.md` 2026-10-18「restricted の到着ターンは接続容量に数えない」(ユーザー判断、`fix/restricted_link_release`)の後、
上と同じ全マップ(revie_case 63枚、配布マップの写し10枚と元のまま10枚、課題の例)を `--visual none` で再実行した。
再生チェッカーは、到着するドローンを接続の使用数に数えないように直した写しを使った(予約を含むゾーン容量の検査はそのまま)。

- 終了コード0の36回すべてで違反0件。エラーで終わるマップの出力は変わらない。
- ターン数が変わったのは3枚: P04_metadata_variants 6 → 5、X11_large_grid 74 → 73、配布マップ the_impossible_dream 43 → 45。
  ほかはすべて同じ。
- **S07 は5ターンのまま**(出力も上の表と同じ)。上の「S07 について」の2つの理由のうち、接続(`s-r`)は2ターン目に空くようになったが、
  `r`(容量1)は到着した D1 で埋まっていて D2 の予約ができない(出発時の予約の規則、2026-10-16。今回は変えていない)。
  そのため S07 の「最適4ターン」は、今の規則でもまだ一致しない。4ターンになるのは `r` の容量が2以上のとき
  (同じ形で `r` を容量2にしたマップで `D1-s-r` / `D1-r D2-s-r` / `D1-g D2-r` / `D2-g`、違反0件を確認)。
- S07 を4ターンにするには、予約の規則も「到着ターンに出ていくドローンの分を使える」ように変える必要がある(未決、ユーザー判断)。
