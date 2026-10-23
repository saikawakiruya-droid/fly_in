# 検証: WSL(Linux)でテストマップの全体実行・部分実行(2026-10-22)

- 日付: 2026-10-22
- 依頼: 表示の改善が終わったら、WSL でテストマップに対して全体・部分実行する。
- 対象のコード: `test/visual_overlaps`(ad1ded6。ラベルと重なりの改善)に `test/trim_run_file` の変更(`run.json` からゾーン・接続の数を外す)を
  当てたもの。ブランチは作らず、scratchpad の作業ツリーで合わせた。
- 環境: WSL2 Ubuntu(Linux 6.18、Python 3.14.4、GNU make)。`~/flyin_check` にコピーして `make install` から実行。
- マップ: 配布マップ10枚(先頭のコメントを除いたもの)、revie_case 75枚(parse_ok・parse_error・sim・edge)、課題の例、
  `docs/research/2026-10-22_visual_review/overlap_demo.txt`。
- 検査の内容(マップごと):
  - 全体: `fly_in.py MAP --visual none` の終了コードとターン数。エラーは1行でトレースバックなし。
  - 部分(パーサーだけ): `--parse-only` で stdout が空。パースエラーのマップは、全体実行と同じエラーの1行・同じ終了コード。
  - 部分(シミュレーションだけ): `--from-world --save-run` のターンログが全体実行と同じ。`run.json` が `complete: true` で、
    各ターンの `log` がターンログと一致し、状態のキーは `delivered_count` と `drones` だけ。
- 結果:
  - `make install`・`make lint`・`make lint-strict` 問題なし。`make test` は 858 passed、1 skipped
    (skip は Windows だけの EINVAL のテストで、Linux では対象外)。`make run` は課題の例を5ターン。
  - 部分実行の検査 194/194 成功。
  - 配布マップのターン数(目標): easy 4/4/4(6/8/6)、medium 8/10/6(12/15/12)、hard 13/16/26(30/35/45)、challenger 44(45未満)。
    ボーナスの条件は Linux でも満たす。
  - パースエラーのマップ(E01〜E40)はすべて終了コード 1 の1行。到達不能(X02・X03・X05)は、パースは通り、シミュレーションで終了コード 1。
- 途中で見つけて直したこと: 1万ゾーンのメッシュでグラフィカル表示の配置に数分かかっていた(決定記録の追記)。1.0 秒になった。

## 出力(WSL)

```text
== make install / lint / test
install OK
.venv/bin/python -m mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
Success: no issues found in 92 source files
Success: no issues found in 92 source files
858 passed, 1 skipped in 2.52s
== make run (subject example)
D4-goal D5-goal
summary: 5 turns, 5 drones, 4.20 turns per drone on average, 3.40 moves per turn
map                                            full  turns  parse via
challenger_01_the_impossible_dream                0     44      0 0
easy_01_linear_path                               0      4      0 0
easy_02_simple_fork                               0      4      0 0
easy_03_basic_capacity                            0      4      0 0
hard_01_maze_nightmare                            0     13      0 0
hard_02_capacity_hell                             0     16      0 0
hard_03_ultimate_challenge                        0     26      0 0
medium_01_dead_end_trap                           0      8      0 0
medium_02_circular_loop                           0     10      0 0
medium_03_priority_puzzle                         0      6      0 0
overlap_demo                                      0      3      0 0
X01_single_drone_start_to_end                     0      1      0 0
X02_disconnected_goal                             1      -      0 1
X03_only_path_blocked                             1      -      0 1
X04_isolated_zone_but_solvable                    0      3      0 0
X05_no_connections                                1      -      0 1
X06_huge_capacity                                 0      1      0 0
X07_huge_nb_drones                                0      1      0 0
X08_many_drones_narrow                            0    201      0 0
X09_dead_end_branch                               0      4      0 0
X10_cycle                                         0      5      0 0
X11_large_grid                                    0     71      0 0
E01_missing_nb_drones                             1      -      1 -
E02_nb_drones_after_zone                          1      -      1 -
E03_nb_drones_zero                                1      -      1 -
E04_nb_drones_negative                            1      -      1 -
E05_nb_drones_not_integer                         1      -      1 -
E06_nb_drones_missing_value                       1      -      1 -
E07_invalid_zone_type                             1      -      1 -
E08_missing_start_hub                             1      -      1 -
E09_missing_end_hub                               1      -      1 -
E10_two_start_hubs                                1      -      1 -
E11_two_end_hubs                                  1      -      1 -
E12_max_drones_zero                               1      -      1 -
E13_max_drones_negative                           1      -      1 -
E14_max_drones_not_integer                        1      -      1 -
E15_link_capacity_zero                            1      -      1 -
E16_link_capacity_float                           1      -      1 -
E17_duplicate_zone_name                           1      -      1 -
E18_duplicate_connection_same_order               1      -      1 -
E19_duplicate_connection_reversed                 1      -      1 -
E20_connection_unknown_zone                       1      -      1 -
E21_connection_before_zone                        1      -      1 -
E22_zone_name_with_dash                           1      -      1 -
E23_coordinate_not_integer                        1      -      1 -
E24_missing_coordinate                            1      -      1 -
E25_metadata_unclosed_bracket                     1      -      1 -
E26_metadata_not_key_value                        1      -      1 -
E27_unknown_metadata_key                          1      -      1 -
E28_link_metadata_on_zone                         1      -      1 -
E29_unknown_keyword                               1      -      1 -
E30_keyword_without_colon                         1      -      1 -
E31_connection_malformed                          1      -      1 -
E32_empty_file                                    1      -      1 -
E33_comments_only                                 1      -      1 -
E34_trailing_garbage                              1      -      1 -
E35_comment_first_line                            1      -      1 -
E36_blocked_start_hub                             1      -      1 -
E37_blocked_end_hub                               1      -      1 -
E38_duplicate_metadata_key                        1      -      1 -
E39_duplicate_key_hides_blocked                   1      -      1 -
E40_blank_first_line                              1      -      1 -
P01_subject_example                               0      5      0 0
P02_defaults                                      0      4      0 0
P04_metadata_variants                             0      5      0 0
P05_start_end_max_drones_ignored                  0      2      0 0
P06_allowed_oddities                              0      3      0 0
S01_single_drone_linear                           0      3      0 0
S02_zone_capacity_default                         0      4      0 0
S03_zone_capacity_two                             0      3      0 0
S04_link_capacity_bottleneck                      0      4      0 0
S05_link_capacity_wide                            0      1      0 0
S06_restricted_transit                            0      3      0 0
S07_restricted_no_wait_on_link                    0      4      0 0
S08_priority_preferred                            0      2      0 0
S09_restricted_vs_detour                          0      3      0 0
S10_blocked_avoided                               0      4      0 0
S11_split_two_paths                               0      3      0 0
S12_link_narrower_than_zone                       0      3      0 0
== partial-run checks: 194/194 passed, 0 failed
== terminal view on a pipe (no colors expected)
=== Turn 0 (start) | 5 drones | 7 zones, 6 connections ===
key: S=start E=end .=normal P=priority R=restricted X=blocked | in/max: -=no limit +N=arriving *=full
  hub       S 5/-        goal      E 0/-        roof1     R 0/1        roof2     . 0/1
== graphical view, headless, delay 0 (window closed by the watchdog-free path: --visual graphical is covered by pytest)
```

## 2回目: develop へのマージ前の検証(ラベル・重なり・拡大縮小・run.json の整理をすべて合わせたもの)

- 対象: develop に `test/trim_run_file` と `test/visual_zoom` をマージした状態(5922314。scratchpad の作業ツリーでマージして検証し、
  同じコミットまで develop を進めた)。マップに `docs/research/2026-10-22_visual_review/arc_stress.txt`(一直線の5ゾーン・弧10本・自己接続)を追加。
- 結果: Windows で flake8・mypy(両方)・pytest 884 passed。WSL で make lint/lint-strict 問題なし、make test 883 passed・1 skipped
  (Windows だけのテスト)、部分実行の検査 197/197 成功。配布マップのターン数は1回目と同じ(challenger 44)。

```text
== make install / lint / test
install OK
.venv/bin/python -m mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
Success: no issues found in 94 source files
Success: no issues found in 94 source files
883 passed, 1 skipped in 3.26s
== make run (subject example)
D4-goal D5-goal
summary: 5 turns, 5 drones, 4.20 turns per drone on average, 3.40 moves per turn
map                                            full  turns  parse via
challenger_01_the_impossible_dream                0     44      0 0
easy_01_linear_path                               0      4      0 0
easy_02_simple_fork                               0      4      0 0
easy_03_basic_capacity                            0      4      0 0
hard_01_maze_nightmare                            0     13      0 0
hard_02_capacity_hell                             0     16      0 0
hard_03_ultimate_challenge                        0     26      0 0
medium_01_dead_end_trap                           0      8      0 0
medium_02_circular_loop                           0     10      0 0
medium_03_priority_puzzle                         0      6      0 0
arc_stress                                        0      6      0 0
overlap_demo                                      0      3      0 0
X01_single_drone_start_to_end                     0      1      0 0
X02_disconnected_goal                             1      -      0 1
X03_only_path_blocked                             1      -      0 1
X04_isolated_zone_but_solvable                    0      3      0 0
X05_no_connections                                1      -      0 1
X06_huge_capacity                                 0      1      0 0
X07_huge_nb_drones                                0      1      0 0
X08_many_drones_narrow                            0    201      0 0
X09_dead_end_branch                               0      4      0 0
X10_cycle                                         0      5      0 0
X11_large_grid                                    0     71      0 0
E01_missing_nb_drones                             1      -      1 -
E02_nb_drones_after_zone                          1      -      1 -
E03_nb_drones_zero                                1      -      1 -
E04_nb_drones_negative                            1      -      1 -
E05_nb_drones_not_integer                         1      -      1 -
E06_nb_drones_missing_value                       1      -      1 -
E07_invalid_zone_type                             1      -      1 -
E08_missing_start_hub                             1      -      1 -
E09_missing_end_hub                               1      -      1 -
E10_two_start_hubs                                1      -      1 -
E11_two_end_hubs                                  1      -      1 -
E12_max_drones_zero                               1      -      1 -
E13_max_drones_negative                           1      -      1 -
E14_max_drones_not_integer                        1      -      1 -
E15_link_capacity_zero                            1      -      1 -
E16_link_capacity_float                           1      -      1 -
E17_duplicate_zone_name                           1      -      1 -
E18_duplicate_connection_same_order               1      -      1 -
E19_duplicate_connection_reversed                 1      -      1 -
E20_connection_unknown_zone                       1      -      1 -
E21_connection_before_zone                        1      -      1 -
E22_zone_name_with_dash                           1      -      1 -
E23_coordinate_not_integer                        1      -      1 -
E24_missing_coordinate                            1      -      1 -
E25_metadata_unclosed_bracket                     1      -      1 -
E26_metadata_not_key_value                        1      -      1 -
E27_unknown_metadata_key                          1      -      1 -
E28_link_metadata_on_zone                         1      -      1 -
E29_unknown_keyword                               1      -      1 -
E30_keyword_without_colon                         1      -      1 -
E31_connection_malformed                          1      -      1 -
E32_empty_file                                    1      -      1 -
E33_comments_only                                 1      -      1 -
E34_trailing_garbage                              1      -      1 -
E35_comment_first_line                            1      -      1 -
E36_blocked_start_hub                             1      -      1 -
E37_blocked_end_hub                               1      -      1 -
E38_duplicate_metadata_key                        1      -      1 -
E39_duplicate_key_hides_blocked                   1      -      1 -
E40_blank_first_line                              1      -      1 -
P01_subject_example                               0      5      0 0
P02_defaults                                      0      4      0 0
P04_metadata_variants                             0      5      0 0
P05_start_end_max_drones_ignored                  0      2      0 0
P06_allowed_oddities                              0      3      0 0
S01_single_drone_linear                           0      3      0 0
S02_zone_capacity_default                         0      4      0 0
S03_zone_capacity_two                             0      3      0 0
S04_link_capacity_bottleneck                      0      4      0 0
S05_link_capacity_wide                            0      1      0 0
S06_restricted_transit                            0      3      0 0
S07_restricted_no_wait_on_link                    0      4      0 0
S08_priority_preferred                            0      2      0 0
S09_restricted_vs_detour                          0      3      0 0
S10_blocked_avoided                               0      4      0 0
S11_split_two_paths                               0      3      0 0
S12_link_narrower_than_zone                       0      3      0 0
== partial-run checks: 197/197 passed, 0 failed
== terminal view on a pipe (no colors expected)
=== Turn 0 (start) | 5 drones | 7 zones, 6 connections ===
key: S=start E=end .=normal P=priority R=restricted X=blocked | in/max: -=no limit +N=arriving *=full
  hub       S 5/-        goal      E 0/-        roof1     R 0/1        roof2     . 0/1
== graphical view, headless, delay 0 (window closed by the watchdog-free path: --visual graphical is covered by pytest)
```

## 3回目: Windows 対応の削除と `simulation/scheduling/` への整理を合わせたマージ前の検証

- 対象: develop に `test/drop_windows_support` と `feature/scheduling_package`(別セッションの作業)をマージした状態(3b40b46)。
  `docs/decisions.md` の末尾の追記どうしの衝突は、両方を残して解消。
- 結果: Windows で flake8・mypy(両方)・pytest 878 passed。WSL で make lint/lint-strict 問題なし、make test は4回とも 878 passed
  (bugs.md の VG08 の不安定な失敗は今回は再現せず)、部分実行の検査 197/197 成功。配布マップのターン数は変わらない。
- 全マップの部分実行の一覧(ユーザーの依頼で作成): `_tmp/partial_runs/summary.md`(2026-10-23 の整理で、表だけを下の「付録」に写し、フォルダは削除)(マップごとの world.json・run.json・標準出力・標準エラー出力も同じフォルダ)。
  正常に終わる 47 枚は `--parse-only` → `--from-world --save-run` のターンログが全体実行と一致。到達不能の3枚(X02・X03・X05)は
  パースは通り、シミュレーションで同じエラー。パースエラーの 40 枚は `--parse-only` でも全体実行と同じ1行のエラー。

## 付録: 全マップの部分実行の一覧(3回目の検証、WSL)

| set | map | full run | --parse-only | --from-world --save-run |
|---|---|---|---|---|
| dist | challenger_01_the_impossible_dream | 44 turns | OK: 54 zones, 70 links, 25 drones | 44 turns, complete=True, log same |
| dist | easy_01_linear_path | 4 turns | OK: 4 zones, 3 links, 2 drones | 4 turns, complete=True, log same |
| dist | easy_02_simple_fork | 4 turns | OK: 5 zones, 5 links, 4 drones | 4 turns, complete=True, log same |
| dist | easy_03_basic_capacity | 4 turns | OK: 4 zones, 3 links, 4 drones | 4 turns, complete=True, log same |
| dist | hard_01_maze_nightmare | 13 turns | OK: 17 zones, 22 links, 8 drones | 13 turns, complete=True, log same |
| dist | hard_02_capacity_hell | 16 turns | OK: 15 zones, 21 links, 12 drones | 16 turns, complete=True, log same |
| dist | hard_03_ultimate_challenge | 26 turns | OK: 31 zones, 37 links, 15 drones | 26 turns, complete=True, log same |
| dist | medium_01_dead_end_trap | 8 turns | OK: 6 zones, 5 links, 5 drones | 8 turns, complete=True, log same |
| dist | medium_02_circular_loop | 10 turns | OK: 7 zones, 7 links, 6 drones | 10 turns, complete=True, log same |
| dist | medium_03_priority_puzzle | 6 turns | OK: 7 zones, 7 links, 5 drones | 6 turns, complete=True, log same |
| extra | arc_stress | 6 turns | OK: 5 zones, 11 links, 6 drones | 6 turns, complete=True, log same |
| extra | overlap_demo | 3 turns | OK: 6 zones, 8 links, 4 drones | 3 turns, complete=True, log same |
| revie/edge | X01_single_drone_start_to_end | 1 turns | OK: 2 zones, 1 links, 1 drones | 1 turns, complete=True, log same |
| revie/edge | X02_disconnected_goal | error | OK: 4 zones, 2 links, 2 drones | `error: goal 'g' is unreachable from 's'` |
| revie/edge | X03_only_path_blocked | error | OK: 3 zones, 2 links, 1 drones | `error: goal 'g' is unreachable from 's'` |
| revie/edge | X04_isolated_zone_but_solvable | 3 turns | OK: 5 zones, 3 links, 2 drones | 3 turns, complete=True, log same |
| revie/edge | X05_no_connections | error | OK: 2 zones, 0 links, 1 drones | `error: goal 'g' is unreachable from 's'` |
| revie/edge | X06_huge_capacity | 1 turns | OK: 2 zones, 1 links, 50 drones | 1 turns, complete=True, log same |
| revie/edge | X07_huge_nb_drones | 1 turns | OK: 2 zones, 1 links, 100000 drones | 1 turns, complete=True, log same |
| revie/edge | X08_many_drones_narrow | 201 turns | OK: 3 zones, 2 links, 200 drones | 201 turns, complete=True, log same |
| revie/edge | X09_dead_end_branch | 4 turns | OK: 6 zones, 5 links, 3 drones | 4 turns, complete=True, log same |
| revie/edge | X10_cycle | 5 turns | OK: 6 zones, 6 links, 3 drones | 5 turns, complete=True, log same |
| revie/edge | X11_large_grid | 71 turns | OK: 625 zones, 1200 links, 40 drones | 71 turns, complete=True, log same |
| revie/parse_error | E01_missing_nb_drones | error | `error: line 1: the first line must be 'nb_drones: <n>'` | - (not parsed) |
| revie/parse_error | E02_nb_drones_after_zone | error | `error: line 1: the first line must be 'nb_drones: <n>'` | - (not parsed) |
| revie/parse_error | E03_nb_drones_zero | error | `error: line 1: n must be a positive integer, got 0` | - (not parsed) |
| revie/parse_error | E04_nb_drones_negative | error | `error: line 1: n must be a positive integer, got -3` | - (not parsed) |
| revie/parse_error | E05_nb_drones_not_integer | error | `error: line 1: n must be an integer, got '2.5'` | - (not parsed) |
| revie/parse_error | E06_nb_drones_missing_value | error | `error: line 1: expected 'nb_drones: <n>', got 'nb_drones:'` | - (not parsed) |
| revie/parse_error | E07_invalid_zone_type | error | `error: line 3: zone must be one of normal, blocked, restricted, priority, got 'fast'` | - (not parsed) |
| revie/parse_error | E08_missing_start_hub | error | `error: line 4: missing start_hub` | - (not parsed) |
| revie/parse_error | E09_missing_end_hub | error | `error: line 4: missing end_hub` | - (not parsed) |
| revie/parse_error | E10_two_start_hubs | error | `error: line 3: duplicate start_hub` | - (not parsed) |
| revie/parse_error | E11_two_end_hubs | error | `error: line 4: duplicate end_hub` | - (not parsed) |
| revie/parse_error | E12_max_drones_zero | error | `error: line 3: max_drones must be a positive integer, got 0` | - (not parsed) |
| revie/parse_error | E13_max_drones_negative | error | `error: line 3: max_drones must be a positive integer, got -2` | - (not parsed) |
| revie/parse_error | E14_max_drones_not_integer | error | `error: line 3: max_drones must be an integer, got 'two'` | - (not parsed) |
| revie/parse_error | E15_link_capacity_zero | error | `error: line 4: max_link_capacity must be a positive integer, got 0` | - (not parsed) |
| revie/parse_error | E16_link_capacity_float | error | `error: line 4: max_link_capacity must be an integer, got '1.5'` | - (not parsed) |
| revie/parse_error | E17_duplicate_zone_name | error | `error: line 4: duplicate zone name: a` | - (not parsed) |
| revie/parse_error | E18_duplicate_connection_same_order | error | `error: line 5: duplicate connection: s-g` | - (not parsed) |
| revie/parse_error | E19_duplicate_connection_reversed | error | `error: line 5: duplicate connection: g-s` | - (not parsed) |
| revie/parse_error | E20_connection_unknown_zone | error | `error: line 4: unknown zone: ghost` | - (not parsed) |
| revie/parse_error | E21_connection_before_zone | error | `error: line 3: unknown zone: g` | - (not parsed) |
| revie/parse_error | E22_zone_name_with_dash | error | `error: line 3: name must not contain '-', got 'bad-name'` | - (not parsed) |
| revie/parse_error | E23_coordinate_not_integer | error | `error: line 3: x must be an integer, got '1.5'` | - (not parsed) |
| revie/parse_error | E24_missing_coordinate | error | `error: line 3: expected 'hub: <name> <x> <y>', got 'hub: a 1'` | - (not parsed) |
| revie/parse_error | E25_metadata_unclosed_bracket | error | `error: line 3: malformed metadata block` | - (not parsed) |
| revie/parse_error | E26_metadata_not_key_value | error | `error: line 3: malformed metadata entry: 'restricted'` | - (not parsed) |
| revie/parse_error | E27_unknown_metadata_key | error | `error: line 3: unknown metadata key(s): speed` | - (not parsed) |
| revie/parse_error | E28_link_metadata_on_zone | error | `error: line 3: unknown metadata key(s): max_link_capacity` | - (not parsed) |
| revie/parse_error | E29_unknown_keyword | error | `error: line 3: unrecognized line: 'tunnel: t 1 0'` | - (not parsed) |
| revie/parse_error | E30_keyword_without_colon | error | `error: line 3: unrecognized line: 'hub'` | - (not parsed) |
| revie/parse_error | E31_connection_malformed | error | `error: line 4: expected 'connection: <name1>-<name2>', got 'connection: s g'` | - (not parsed) |
| revie/parse_error | E32_empty_file | error | `error: line 0: map file is empty, expected 'nb_drones: <n>' as the first line` | - (not parsed) |
| revie/parse_error | E33_comments_only | error | `error: line 1: the first line must be 'nb_drones: <n>'` | - (not parsed) |
| revie/parse_error | E34_trailing_garbage | error | `error: line 3: malformed metadata block` | - (not parsed) |
| revie/parse_error | E35_comment_first_line | error | `error: line 1: the first line must be 'nb_drones: <n>'` | - (not parsed) |
| revie/parse_error | E36_blocked_start_hub | error | `error: line 2: start_hub cannot have zone=blocked` | - (not parsed) |
| revie/parse_error | E37_blocked_end_hub | error | `error: line 4: end_hub cannot have zone=blocked` | - (not parsed) |
| revie/parse_error | E38_duplicate_metadata_key | error | `error: line 3: duplicate metadata key 'color'` | - (not parsed) |
| revie/parse_error | E39_duplicate_key_hides_blocked | error | `error: line 2: duplicate metadata key 'zone'` | - (not parsed) |
| revie/parse_error | E40_blank_first_line | error | `error: line 1: the first line must be 'nb_drones: <n>'` | - (not parsed) |
| revie/parse_ok | P01_subject_example | 5 turns | OK: 7 zones, 6 links, 5 drones | 5 turns, complete=True, log same |
| revie/parse_ok | P02_defaults | 4 turns | OK: 3 zones, 2 links, 3 drones | 4 turns, complete=True, log same |
| revie/parse_ok | P04_metadata_variants | 5 turns | OK: 4 zones, 3 links, 2 drones | 5 turns, complete=True, log same |
| revie/parse_ok | P05_start_end_max_drones_ignored | 2 turns | OK: 3 zones, 2 links, 4 drones | 2 turns, complete=True, log same |
| revie/parse_ok | P06_allowed_oddities | 3 turns | OK: 4 zones, 4 links, 1 drones | 3 turns, complete=True, log same |
| revie/sim | S01_single_drone_linear | 3 turns | OK: 4 zones, 3 links, 1 drones | 3 turns, complete=True, log same |
| revie/sim | S02_zone_capacity_default | 4 turns | OK: 3 zones, 2 links, 3 drones | 4 turns, complete=True, log same |
| revie/sim | S03_zone_capacity_two | 3 turns | OK: 3 zones, 2 links, 4 drones | 3 turns, complete=True, log same |
| revie/sim | S04_link_capacity_bottleneck | 4 turns | OK: 3 zones, 2 links, 3 drones | 4 turns, complete=True, log same |
| revie/sim | S05_link_capacity_wide | 1 turns | OK: 2 zones, 1 links, 3 drones | 1 turns, complete=True, log same |
| revie/sim | S06_restricted_transit | 3 turns | OK: 3 zones, 2 links, 1 drones | 3 turns, complete=True, log same |
| revie/sim | S07_restricted_no_wait_on_link | 4 turns | OK: 3 zones, 2 links, 2 drones | 4 turns, complete=True, log same |
| revie/sim | S08_priority_preferred | 2 turns | OK: 4 zones, 4 links, 1 drones | 2 turns, complete=True, log same |
| revie/sim | S09_restricted_vs_detour | 3 turns | OK: 5 zones, 5 links, 1 drones | 3 turns, complete=True, log same |
| revie/sim | S10_blocked_avoided | 4 turns | OK: 5 zones, 5 links, 2 drones | 4 turns, complete=True, log same |
| revie/sim | S11_split_two_paths | 3 turns | OK: 4 zones, 4 links, 4 drones | 3 turns, complete=True, log same |
| revie/sim | S12_link_narrower_than_zone | 3 turns | OK: 3 zones, 2 links, 2 drones | 3 turns, complete=True, log same |
