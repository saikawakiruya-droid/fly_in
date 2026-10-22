# 検証: WSL(Linux)でテストマップの全体実行・部分実行(2026-10-22)

- 日付: 2026-10-22
- 依頼: 表示の改善が終わったら、WSL でテストマップに対して全体・部分実行する。
- 対象のコード: `test/visual_overlaps`(ad1ded6。ラベルと重なりの改善)に `test/trim_run_file` の変更(`run.json` からゾーン・接続の数を外す)を
  当てたもの。ブランチは作らず、scratchpad の作業ツリーで合わせた。
- 環境: WSL2 Ubuntu(Linux 6.18、Python 3.14.4、GNU make)。`~/flyin_check` にコピーして `make install` から実行。
- マップ: 配布マップ10枚(先頭のコメントを除いたもの)、revie_case 75枚(parse_ok・parse_error・sim・edge)、課題の例、
  `_tmp/visual_review/overlap_demo.txt`。
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
