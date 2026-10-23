# 2026-10-23 マップ作成後の検証についての質問

開始: 2026-10-23

## 依頼1: start と end がつながっていないとどうなるか。確認と距離計算は同時か

- パースは成功し、`Pathfinder.__init__` で `DistanceMap`(end 起点の Dijkstra)を作った直後、start の距離が `None` なら
  `UnreachableGoalError`(`goal 'g' is unreachable from 's'`、終了コード 1)。`X02_disconnected_goal.txt` で実行して確認した。
- 到達できるかの判定は距離計算の結果をそのまま使っており、同時(別の探索は書いていない)。decisions.md 2026-10-16 の決定どおり。
- `--parse-only` は Pathfinder を作る前に終わるので、到達できないマップでも World ファイルを書き出す(現状の設計どおり)。

## 依頼2: ほかにマップ作成後の検証はあるか。ファイル構成で分かるか

マップを読み終えた後の検証:

1. `parsing/map_validator.py` の `MapValidator.finish`: ヘッダ(`nb_drones`)があるか、start / end があるか(ファイル全体を見ないと分からないもの)。
2. `pathfinding/pathfinder.py` の `Pathfinder.__init__`: start から end に到達できるか。
3. 実行中: `simulation/turn_resolver.py`(毎ターンの命令と容量の検査)、`simulation/engine.py`(誰も動かないターン、`max_turns` 超過)、
   `simulation/scheduling/scheduler.py`(到達できないゾーンにドローンがいる)。
4. 念のための検査: `models/network.py` の `start_zone` / `end_zone`(ちょうど 1 つでなければ `SimulationError`。パーサーが保証するので通常は起きない)。
5. `--from-world` の場合は `interchange/world_file.py` が同じ `Rule` を適用する。

ファイル構成との対応: parsing / pathfinding / simulation の段階ごとに分かれていて、どこで何を検証するかはおおむね追える。
ただし README のフォルダ構成の図では `pathfinding/` の説明に到達できるかの確認が書かれておらず、本文(パイプラインの説明)や
`docs/review_guide.md` を読まないと分からない。変更は提案のみで、未決。

## 作成・変更したファイル

- `docs/conversation_log/2026-10-23/01_map_validation_qa.md`(このファイル)

## 依頼3: scheduler.py の「到達できないゾーンにいる」検査と、Network の start/end 検査は、一方通行が無いなら不要では

- 通常の実行では、どちらも発生しない。理由は一方通行が無いことに加えて、Scheduler が `next_hops` / `detour_hops`
  (距離が `None` のゾーンを除外済み)からしか移動先を選ばないため。一方通行があっても Scheduler 自身はそのゾーンに入らない。
- ただし、どちらも `int | None` / 見つからない場合を型の上で処理する必要があり、その処理として例外を出している。
  `ZoneRanking.rank` の戻り値は `int | None`、`Network` はパーサーを通さずにコード内で直接組める(decisions.md 2026-10-16 で「直接組んだネットワーク向けの防御」として残すと決定済み)。
  `tests/simulation/scheduling/test_scheduler.py:737` は、この検査を直接テストしている。
- 提案: 残す(消すと mypy を通すために別の書き方が必要で、得るものが少ない)。

## 依頼4: 残すほうで確定

- 決定: 両方の検査を残す。`docs/decisions.md` に「2026-10-23: 通常の実行では起きない到達不能・start/end の検査を残す」として記録した。
