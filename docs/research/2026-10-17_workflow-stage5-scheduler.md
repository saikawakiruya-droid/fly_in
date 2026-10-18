# ワークフロー: Stage 5(Multi-Drone Scheduler)詳細

- 日付: 2026-10-17
- 依頼内容: 残りステージの実装(`docs/decisions.md` 2026-10-16「残りステージの実装方針」)の第3弾として、
  Stage 5 の着手前の設計整理を行う
- 前提:
  - `docs/research/2026-09-17_workflow-all-stages.md` の Stage 5 を詳細化したもの。
  - 判断の順序はユーザーの設計(`docs/decisions.md` 2026-10-16「残りステージの実装方針」2)を、
    2026-10-17 のユーザー判断で「飛行中 → ゴールに近い順 → 同じ距離の中で優先ルートを先 → ID順」に改めたもの
    (`docs/decisions.md` 2026-10-17「判断の順序を『距離が近い順』を先にし…」)。
  - 移動先の候補は `Pathfinder.next_hops`(最短の一手だけ。priority は同点の中で先頭)をそのまま使い、
    **遠回りはしない**(同 3、2026-10-16「距離が最小の隣接ゾーン…」「priority は次の1手の同点の中だけで優先する」)。
  - ルール(容量の数え方・restricted の予約・接続は双方向で共有)は Stage 4 の `TurnResolver` と同じ
    (`docs/decisions.md` 2026-10-16「Stage 4 の API」「restricted への移動は…」「容量の数え方…」)。

## ゴール

`Scheduler.decide_moves(state) -> list[MoveOrder]` を実装し、配布マップすべてで `nb_drones` 全機を
ルール違反なく goal に届ける。

- 飛行中(restricted へ移動中)のドローンには指示を出さない(エンジンが着地させる)。
- 「ゴールまでの距離が近いゾーンにいるドローン」から順に判断する。同じ距離の中では「優先ルート上のドローン」を先にし、
  それでも同じならドローンID順。
- 各ドローンは `next_hops` の候補を先頭から見て、**このターンまだ空きがある最初の候補**へ進む。
  どの候補にも空きがなければ待機する(指示を出さない)。
- 空きの判定は、そのターンにすでに出した指示を反映した**台帳(`TurnLedger`)**で行い、
  `TurnResolver` が拒否しない指示だけを出す。

### 「優先ルート上のドローン」の定義

ゾーンにいるドローンのうち、次のどちらかに当てはまるもの。

1. 今いるゾーンが `zone=priority`。
2. `next_hops(今いるゾーン)` の先頭が `zone=priority`(= 最短の一手の中に priority のゾーンがある。
   `next_hops` は priority を先頭に並べるため、先頭を見れば足りる)。

「2手先以降に priority がある」ことは見ない(2026-10-16「priority は次の1手の同点の中だけで優先する」と同じ範囲に揃える)。
優先ルートかどうかは、同じ距離のドローンの中の順序(タイブレーク)にだけ使う。

## 対象ファイル

| ファイル | 内容 | 状態 |
|---|---|---|
| `droneflow/simulation/turn_ledger.py` | `TurnLedger`(1ターン分の指示を反映したゾーンの空き・接続の使用数) | 新規 |
| `droneflow/simulation/scheduler.py` | `Scheduler.decide_moves`(判断の順序、候補の選択、台帳への記録) | スケルトンを置き換え |

`Pathfinder` / `SimulationState` / `TurnResolver` / `SimulationEngine` は変更しない(読むだけ)。

## 構造図(静的な形)

```mermaid
classDiagram
    class Network {
        <<Stage 1>>
        +get_zone(name) Zone
    }
    class Pathfinder {
        <<Stage 3>>
        +distance(zone) int | None
        +next_hops(zone) Hop[]
    }
    class Hop {
        <<frozen>>
        +connection : Connection
        +zone : Zone
    }
    class SimulationState {
        <<Stage 4>>
        +drones : dict~int, Drone~
        +free_capacity(zone) int | None
        +link_load(connection) int
    }
    class MoveOrder {
        <<frozen>>
        +drone_id : int
        +zone : str
    }
    class TurnLedger {
        <<1ターン限り>>
        -state : SimulationState
        -zone_change : dict~str, int~
        -link_use : dict~str, int~
        +has_room(hop) bool
        +record(from_zone, hop)
    }
    class Scheduler {
        +network : Network
        +pathfinder : Pathfinder
        -hops : dict~str, Hop[]~
        +decide_moves(state) MoveOrder[]
        +is_on_priority_route(zone) bool
        -decision_order(state) Drone[]
        -first_free_hop(zone, ledger) Hop | None
    }
    class TurnResolver {
        <<Stage 4>>
        +resolve(state, orders) Move[]
    }

    Scheduler o-- Pathfinder : 候補(最短の一手)を聞く
    Scheduler --> Network
    Scheduler ..> TurnLedger : 毎ターン作って使い捨て
    Scheduler ..> SimulationState : 読むだけ
    Scheduler ..> MoveOrder : 生成
    TurnLedger --> SimulationState : 空き・接続の負荷を読む
    TurnLedger ..> Hop : 判定する
    Pathfinder ..> Hop : 生成
    TurnResolver ..> MoveOrder : 検査する(同じ規則)
```

継承は使わない。`Scheduler` は `Pathfinder` を持ち(委譲)、1ターンの数え上げは `TurnLedger` に任せる。
`TurnLedger` は `TurnResolver` と同じ規則を「指示を1つ足すごとに」判定できる形にしたもの。

### `TurnLedger` の数え方(`TurnResolver` と同じ規則)

| 対象 | 空きの判定 | 指示を記録したときの変化 |
|---|---|---|
| ゾーン z(start / end 以外) | `state.free_capacity(z) − 変化(z) ≥ 1` | 出発元 −1、移動先 +1 |
| ゾーン z(start / end) | 常に空きあり(`free_capacity` が None) | 記録はするが判定に使わない |
| 接続 c | `使用数(c) < max_link_capacity` | 使用数 +1(向きは区別しない) |

- `free_capacity` は「いる数+予約数」から求めるので、restricted の予約(飛行中の分)は最初から埋まっている。
  restricted へ出発する指示は、移動先に +1 するだけで予約の規則と一致する(`TurnResolver` も出発時に数える)。
- 飛行中(このターンに着地する)ドローンは着地で接続を空けるので、接続の使用数には数えない(2026-10-18 に改めた。当初は `state.link_load(c)` を足し、着地で使う接続も最初から埋まっているとしていた)。
- 退出(−1)は記録した時点から空きとして使える。最終的な負荷で判定する `TurnResolver` に対し、
  台帳は「途中までの指示」で判定するので、後から退出が増えても違反にはならない(保守的)。

## 挙動図(実行時の振る舞い)

### (a) 1回の `decide_moves` の流れ

```mermaid
flowchart TD
    A["decide_moves(state)"] --> B["ledger = TurnLedger(state)"]
    B --> C["ゾーンにいるドローン(AT_ZONE)を集める<br/>(飛行中・配達済みは除外)"]
    C --> D["並べる: 距離が近い順 → 同距離なら優先ルート上を先 → ドローンID順"]
    D --> E{"次のドローンがいる?"}
    E -- いいえ --> Z["orders を返す"]
    E -- はい --> F["hops = next_hops(今いるゾーン)<br/>(最短の一手のみ・priority が先頭)"]
    F --> G{"ledger.has_room(hop) の候補がある?<br/>(先頭から順に見る)"}
    G -- いいえ --> E
    G -- はい --> H["ledger.record(今いるゾーン, hop)<br/>orders に MoveOrder(id, hop.zone.name)"]
    H --> E
```

### (b) エンジンとのやり取り(1ターン)

例: `start - a - goal`(a は容量1)、ドローン2機。ターン2で D1 が a を出て、同じターンに D2 が a に入る。

```mermaid
sequenceDiagram
    participant Eng as SimulationEngine
    participant Sch as Scheduler
    participant Led as TurnLedger
    participant PF as Pathfinder
    participant St as SimulationState
    participant Res as TurnResolver

    Note over Eng,St: ターン2の開始時: D1 は a、D2 は start
    Eng->>Sch: decide_moves(state)
    Sch->>Led: TurnLedger(state)
    Sch->>St: AT_ZONE のドローンを集める
    Sch->>Sch: 並べる → D1(距離1)、D2(距離2)
    Sch->>PF: next_hops("a") → [goal]
    Sch->>Led: has_room(a→goal)? → はい(goal は無制限、接続は空き)
    Sch->>Led: record("a", goal)(a の変化 −1)
    Sch->>PF: next_hops("start") → [a]
    Sch->>Led: has_room(start→a)? free(a)=0 − 変化(−1) = 1 ≥ 1 → はい
    Sch->>Led: record("start", a)(a の変化 0)
    Sch-->>Eng: [MoveOrder(1, "goal"), MoveOrder(2, "a")]
    Eng->>Res: resolve(state, orders)
    Res->>Res: 同じ規則で検査(最終負荷 a = 1 ≤ 1)
    Res-->>Eng: [Move(1, "goal"), Move(2, "a")]
```

## デッドロックが起きない理由

この方針では、移動は必ず「ゴールまでの距離が真に小さいゾーン」への移動になる(`next_hops` は
`turn_cost(v) + dist(v) = dist(u)` を満たす v だけを返し、`turn_cost ≥ 1`)。そのため次が言える。

1. 飛行中のドローンがいれば、そのターンは必ず着地があり、誰かが動く。
2. 飛行中のドローンがいなければ、ゾーンにいるドローンのうち距離が最小の1機 D(ゾーン u)を考える。
   D の候補 v は `dist(v) < dist(u)` なので、v には誰もいない(全員の距離は `dist(u)` 以上)し、予約もない(飛行中がいない)。
   接続にも飛行中のドローンはいない。D より先に判断されたドローンが誰も指示を受けていなければ、v にも接続にも空きがあり
   (容量は正の整数)、D は動ける。誰かが先に指示を受けていれば、その時点で動くドローンがいる。
3. よって毎ターン少なくとも1機が動き(または着地し)、「誰も動かないターン」(`SimulationError`)は起きない。
4. 1回の動き(着地を含む)ごとに、全機の「残り距離の合計」が1以上減る(restricted は出発と着地で計2)。
   合計の初期値は `nb_drones × dist(start)` 以下なので、ターン数もこれ以下で必ず終わる。
   `dist(start) ≤ 2 × (ゾーン数 − 1)` なので、エンジンの上限 `2 × ゾーン数 × nb_drones` を超えることもない。

相互待ち(A が B の空きを、B が A の空きを待つ)は、距離が単調に減る向きにしか動かないため構造的に起きない。

### 距離順を先にする理由(当初の「優先ルートを先」から変更)

当初は優先ルートのドローンを距離に関係なく先に判断していた。その場合、優先ルートのドローンの移動先に
「まだ判断されていない(このあと出ていく)ドローン」がいると、退出が台帳に載っておらず満員に見えて1ターン待ってしまう
(課題の例で下限7ターンに対し11ターン)。距離が近い順を先にすると、移動先(距離が真に小さいゾーン)にいるドローンは
必ず先に判断済みなので、同じターンの退出で空いた分を常に使える。1周の判断で足りる。

## 作業項目

1. `turn_ledger.py`: `TurnLedger(state)` を実装する(`has_room(hop)`、`record(from_zone, hop)`)。
2. `scheduler.py`: `Scheduler(network, pathfinder)` を実装する(`next_hops` のゾーンごとのキャッシュ、
   `is_on_priority_route(zone)`、判断の順序、最初の空き候補の選択、`decide_moves`)。
3. 配布マップ10枚と課題の例で `MapParser → Pathfinder → Scheduler → SimulationEngine` を通し、
   ターン数を課題の目標(VII.7)と比べる(アドホック、コミットしない)。結果は
   `docs/research/2026-10-17_stage5-benchmark.md` に記録する。
4. `flake8` / `mypy --strict` / 既存テストを通す。

## スコープ外

- 遠回り(最短でない一手)による負荷分散・戦略的な迂回(ユーザー判断で採らない)。
- 時間展開の予約方式など、別方式のスケジューラ(2026-10-16 の代替案)。
- 目標ターン数に合わせたアルゴリズムの調整(届かない場合は原因と選択肢を報告するだけ)。
- `app.py` / `cli.py` での組み立て(別ステージ)。
- 単体テストの作成(別のテスト設計・作成フェーズで行う)。

## 完了条件(Done)

- `droneflow/simulation/scheduler.py` に `NotImplementedError` が残っていない。
- 配布マップ10枚と課題の例で、全機が `SimulationError` なしに goal に着く。
- 既存テストがすべて通り、`flake8` と `mypy --strict` がエラーなしで通る。

## レビュー時の確認事項

- 飛行中のドローンに指示を出していないか。配達済みのドローンを判断に含めていないか。
- 候補は `next_hops` だけか(遠回りや自己ループの移動をしていないか)。
- 台帳の規則が `TurnResolver` と一致しているか(退出で空く、restricted は出発時に数える、接続は双方向で共有、
  飛行中のドローンの接続使用を最初から数える、start / end は数えない)。
- 判断の順序が「距離が近い順 → 同距離なら優先ルート → ID順」になっているか。優先ルートの定義が上記どおりか。
- `docs/decisions.md` の 2026-10-16 の各決定(特に priority の扱い、遠回りしない)と食い違っていないか。
- `docs/bugs.md` に記録すべき不整合が残っていないか。
