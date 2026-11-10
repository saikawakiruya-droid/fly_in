# 2026-11-10 アルゴリズム(経路探索・スケジューラ)の現状の構成

ユーザーの依頼: 「アルゴリズムがめんどいことになっているため修正する。まず今の構成を教えて」。
修正前の現状把握として、develop 325d4ad 時点の構成を整理した。

## 全体の流れ

`app.py` → `Pathfinder(network)` → `Scheduler(network, pathfinder)` → `Engine`。
毎ターン `Engine` が `Scheduler.decide_moves(state)` で命令を受け取り、`TurnResolver` が合法性を確認して適用する。

## ファイルと役割(アルゴリズム部分 約1,900行)

| ファイル | 行数 | 役割 |
|---|---|---|
| pathfinder_distance_map.py | 75 | ゴールから逆向きのダイクストラ1回。各ゾーン→ゴールのターン数 |
| pathfinder.py | 174 | `next_hops`(最短の次の一手、priority 優先)、`detour_hops`(最短でない一手)、`route_cost` |
| scheduler.py | 257 | 毎ターンの司令塔。予約済みの移動 → ゾーン順に各ドローンを決定 |
| scheduler_zone_ranking.py | 87 | 決定順: 距離が近い順 → priority 経路 → 出口が少ない → 宣言順 |
| scheduler_hop_taker.py | 148 | 候補の一手を順に試す。1周目は追い出しなし、2周目は追い出しあり |
| scheduler_turn_ledger.py | 196 | このターン以降のゾーン・接続の空き(予測負荷)を数える |
| scheduler_reservation_table.py | 299 | 複数ターン先までの予約(restricted への着陸、追い出し)。mark/rollback 付き |
| scheduler_evictor.py | 144 | 満員ゾーンの占有者を後のターンに最短方向へ押し出す予約を、再帰的に作る |
| scheduler_detour_policy.py | 184 | 迂回の許可: 未訪問ゾーンのみ、`cost(v)+dist(v)+queue(v) <= dist(u)+ahead(u)`。訪問履歴をターンごとに保持 |
| scheduler_positions.py | 123 | ターン計画中の各ドローンの位置(PositionBoard) |

## 1ドローンの決定手順(`Scheduler._decide`)

1. 自分の追い出し予約があれば一旦外す
2. 最短の一手を、空きがあるものから順に(追い出しなし)
3. 同じ一手を、追い出しありで(restricted: 着陸ターンから席を空ける / 通常: 入ってから自分を含めて追い出す)
4. `DetourPolicy` が許す迂回を、同じ2段階で
5. どれも無理なら待機し、このドローンの分の予約を rollback

## 複雑さの主な原因(観察)

- 状態が4か所に分散: ReservationTable(複数ターン先)、TurnLedger(このターンの数え上げ + 予約の投影)、
  PositionBoard(位置)、DetourPolicy(訪問履歴)
- 追い出し(Evictor)が再帰 + rollback で、予約が複数ターンに伸びる
- 同じターンの再計画・過去ターンからのやり直しへの対応(rollback / clear / `_forget_from`)
- 1手を試す経路が「最短/迂回」×「追い出しなし/あり」×「restricted/通常」の組み合わせ

## 追記(同日): ファイルが13本にまとめられた

この記録のあと、別の作業(65f6e4f、develop 9da665f にマージ)でソースファイルが34本から13本にまとめられた。
上の表のファイル名は当時のもの。中身(クラスと手順)はそのまま、`scheduler.py`・`engine.py` などに入っている。
