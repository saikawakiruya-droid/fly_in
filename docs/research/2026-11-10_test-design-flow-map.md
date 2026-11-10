# テスト設計: フローマップによるスケジューラ(`pathfinder.py` / `scheduler.py` / `Drone.history`)

- 日付: 2026-11-10
- フェーズ: **テスト設計**(このファイルにはテストコードを書かない。作成は別のエージェントが行う)
- 対象ブランチ: `feature/flow_map_scheduler`(コミット `0557090` Drone.history、`d7bf19a` フローマップ、`5ace91d` 古いテストの削除)
- 対象コード:
  - `pathfinder.py`: `Route`(`zones` / `rate` / `turns` / `arrival_turn`)、`last_turn(routes, nb_drones)`、`FlowMap`
    (`network` = 押さえた地図 / `routes` / `last_turn`)、`FlowGraph`(残余グラフ。ゾーンを in/out に分ける)、`Pathfinder`
  - `scheduler.py`: `Departure`、`plan_departures(flow_map, nb_drones)`、`Scheduler`(`flow_map` プロパティ、`decide_moves`)
  - `engine.py`: `Drone.history`(`SimulationState.__init__` が `[start]` を入れ、`_arrive` が入ったゾーンを足す)
- 変更されていないので対象外(結合として使うだけ): `world.py`、`TurnResolver`、`SimulationEngine`、パーサー
- 書式の手本: `docs/research/2026-10-17_test-design-stage5-scheduler.md`、`docs/research/2026-10-16_test-design-stage3-pathfinding.md`

## 方針

- 期待値はすべて、設計時にこのブランチの実装で実行して確かめた(scratchpad のアドホックなスクリプト。コミットしない)。
- 小さなネットワークは `make_network`(`tests/conftest.py` の `build_network`)で組む。記法は `make_network("s-a a-g", types=..., capacity=..., links=...)`。
  - 注意: `make_network` はゾーンを「start, end, 出てきた順」で登録する。ハブの `max_drones` は指定がなければ 1、接続の容量も 1。
- ドローンの配置は検査をしない基本操作(共有の `place` = `place_drones`、`state.enter_zone` / `enter_transit`)で作ってよい。
  これらも `history` に足すので、置き方の順に `history` が積まれる(`place(net, 1, at={1: "b"})` → `["s", "b"]`)。
- 「壊れたフローマップ」を渡すテスト(SC 系のエラー)は、本物の `Pathfinder` のインスタンスの `flow_map` を
  `monkeypatch.setattr(pathfinder, "flow_map", lambda nb_drones: fixed)` で差し替えて作る。`Scheduler` の引数の型は
  `Pathfinder` なので、別のクラスで包むと mypy に通らない。継承したスタブより差し替えの方が小さい(合成を優先する方針とも矛盾しない)。
- `FlowMap` は frozen の dataclass だが、`network`(`Network`)に `__eq__` が無いので、`FlowMap` 同士の `==` は使えない。
  比べるときは `routes` と `last_turn`、押さえた地図の中身(下のヘルパー)を別々に比べる。`Route` / `Departure` は値で比べられる。
- テスト同士は import しない(従来どおり、共有するものは conftest のフィクスチャで渡す)。

## ファイル構成

```
tests/
├── conftest.py                         # 変更なし(take_snapshot に history を足すかは「確認したい点」1)
├── models/
│   └── test_drone.py                   # 追記: DH01
├── pathfinding/
│   ├── conftest.py                     # 変更なし(grid_network をそのまま使う)
│   └── test_flow_map.py                # 新規: LT01〜LT07, FM01〜FM16, HM01〜HM08, PF01〜PF05
└── simulation/
    ├── conftest.py                     # 追記: fixed_scheduler(下記)
    ├── test_state.py                   # 追記: DH02〜DH07
    └── scheduling/
        ├── test_scheduler.py           # 新規: PD01〜PD09, SC01〜SC20
        └── test_scheduler_maps.py      # 書き換え: R01〜R20 の残す・直す・捨てる(下記 3章)
```

- ID の接頭辞: `LT` = last_turn / Route、`FM` = フロー(経路の見つけ方と分け方)、`HM` = Held Map(押さえた地図)、
  `PF` = Pathfinder の構築・E2E、`PD` = plan_departures、`SC` = Scheduler、`DH` = Drone.history。
  既存・削除済みの ID(`FG` は削除した詰まり検出の設計で使っていた、`D` / `H` / `P` / `N` は削除したテスト)と重ならない。

### ヘルパー(各テストファイルの中に置く。共有しない)

| 名前 | 中身 | 使うファイル |
|---|---|---|
| `route(text, rate, turns) -> Route` | `Route(tuple(text.split()), rate, turns)`。例 `route("s a g", 1, 2)` | test_flow_map / test_scheduler |
| `zone_caps(network) -> dict[str, int \| None]` | `{name: zone.max_drones for name, zone in network.zones.items()}`(宣言順の dict) | test_flow_map |
| `link_caps(network) -> list[tuple[str, int]]` | `[(c.name, c.max_link_capacity) for c in network.connections]` | test_flow_map |
| `summary(departures) -> dict[int, tuple[str, int]]` | `{id: (d.route.zones[1], d.turn)}`(最初に入るゾーンと出発ターン) | test_scheduler(PD 系) |

### 共有フィクスチャ(`tests/simulation/conftest.py` に追記)

| 名前 | 中身 |
|---|---|
| `fixed_scheduler(network, flow_map) -> Scheduler` | `pathfinder = Pathfinder(network)` を作り、`monkeypatch.setattr(pathfinder, "flow_map", lambda nb_drones: flow_map)` で差し替えた `Scheduler(network, pathfinder)` を返すファクトリ(フィクスチャ内で `monkeypatch` を受け取る) |

既存の `real_scheduler`(`Scheduler(network, Pathfinder(network))`)、`place`、`snapshot` はそのまま使う。

---

## 2. テストケース

### 2.1 `tests/pathfinding/test_flow_map.py`(36 件)

#### `last_turn` と `Route.arrival_turn`(LT)

| ID | 対象 | 入力 | 期待値 | 理由 |
|---|---|---|---|---|
| LT01 | `last_turn` ドローン0 | `last_turn((), 0)`、`last_turn((route("s g", 1, 1),), -3)` | どちらも `0` | 0 機のときは経路が無くても例外にしない(`flow_map(0)` が使う) |
| LT02 | `last_turn` 経路なし | `last_turn((), 1)` | `ValueError`、メッセージ `no route to send the drones along` | 経路がないのに機がいるのは呼び出し側の誤り |
| LT03 | 経路1本・rate 1 | `route("s a b g", 1, 3)` で N=1, 2, 4 | `3, 4, 6`(= turns + N − 1) | 1列に流すときの基本形 |
| LT04 | 経路1本・rate 2 | `route("s a g", 2, 2)` で N=1, 2, 3, 4, 5 | `2, 2, 3, 3, 4` | 1ターンに rate 機ずつ届く。割り切れない数の切り上げ |
| LT05 | 経路2本(長さ違い) | `route("s a g", 1, 2)` と `route("s r g", 1, 3)` で N=1〜5 | `2, 3, 3, 4, 4` | 式 `Σ rate·max(0, T − turns + 1) ≥ N` の和。T=3 で 2+1=3 機 |
| LT06 | T より長い経路は数えない | `route("s a g", 1, 2)` と `route("x", 1, 10)` で N=1, 3, 8, 9, 10 | `2, 4, 9, 10, 10` | `max(0, …)` が効くこと。N=10 では長い経路も1機運ぶので 10(9 ではない) |
| LT07 | `Route.arrival_turn` | `route("s a g", 1, 2).arrival_turn(1)` / `(3)` | `2` / `4`(= depart + turns − 1) | 出発ターンにもう1ゾーン目に入る数え方 |

#### フローと経路の分け方(FM。`Pathfinder(net).flow_map(N)` の `routes` と `last_turn`)

経路は `Route(zones, rate, turns)` で書く。

| ID | 対象 | 入力 | 期待値 | 理由 |
|---|---|---|---|---|
| FM01 | 一本道 | `make_network("s-a a-g")`、N=3 | routes `(Route(("s","a","g"),1,2),)`、last_turn `4` | 最小の形 |
| FM02 | 分岐・1機 | `make_network("s-a a-g s-b b-g")`、N=1 | routes は `s a g` の1本だけ、last_turn `2` | 同じ長さなら宣言順で先の方。1機には2本目は要らない |
| FM03 | 分岐・2機以上 | 同じ網で N=2 / N=5 | routes `(s a g, 1, 2)`, `(s b g, 1, 2)` の順。last_turn は N=2 で `2`、N=5 で `4` | 2本に分けて流す |
| FM04 | 細いゾーンへの合流 | `make_network("s-a s-b a-m b-m m-g")`(m の容量 1)、N=3 | routes `(s a m g, 1, 3)` の1本だけ、last_turn `5` | 合流先の容量で全体が1機/ターンに絞られる。b は使わない |
| FM05 | 合流先が広い | `make_network("s-a s-b a-m b-m m-g", capacity={"m": 2}, links={"m-g": 2})`、N=4 | routes `(s a m g,1,3)`, `(s b m g,1,3)`、last_turn `4` | 2本が同じゾーン m を共有できる |
| FM06 | 接続容量が詰まる場所 | `make_network("s-a a-g", capacity={"a": 3}, links={"s-a": 2, "a-g": 3})`、N=4 | routes `(s a g, 2, 2)`、last_turn `3` | rate はゾーン容量ではなく接続容量 2 で決まる |
| FM07 | ゾーン容量が詰まる場所 | `make_network("s-a a-g", capacity={"a": 1}, links={"s-a": 3, "a-g": 3})`、N=4 | routes `(s a g, 1, 2)`、last_turn `5` | 逆に、ゾーンの in→out の弧の容量 1 で決まる |
| FM08 | restricted は 2 ターン | `make_network("s-r r-g", types={"r": R})`、N=2 | routes `(s r g, 1, 3)`、last_turn `4` | 進入コスト 2 が `turns` に入る |
| FM09 | restricted の回り道を使う・使わない | `make_network("s-a a-g s-r r-g", types={"r": R})`、N=1 / 2 / 3 | N=1: `(s a g,1,2)` のみ・T=2。N=2: `(s a g,1,2)` のみ・T=3。N=3: `(s a g,1,2)`, `(s r g,1,3)`・T=3 | N=2 では r(長さ3)を足しても T が下がらないので足さない(打ち切りの条件 `turns ≥ best T`)。N=3 で初めて使う |
| FM10 | T が下がらない経路は残さない | `make_network("s-a a-g s-b b-g", capacity={"a": 2}, links={"s-a": 2, "a-g": 2})`、N=4 / N=5 | N=4: `(s a g, 2, 2)` だけ・T=3。N=5: `(s a g,2,2)`, `(s b g,1,2)`・T=3 | N=4 では b を足しても T=3 のまま(厳密に小さくなったときだけ更新する)。同じ網でも N で残る経路が変わる |
| FM11 | priority の同点の優先 | `make_network("s-a a-g s-p p-g", types={"p": P})`、N=1 / N=2 | N=1: `(s p g,1,2)`(a が先に宣言されていても p)。N=2: `(s p g,1,2)`, `(s a g,1,2)` の順 | 同じ長さなら priority を通る方が安い。`routes` も priority を先に並べる |
| FM12 | 長い priority は選ばない | `make_network("s-p p-q q-g s-a a-g", types={"p": P})`、N=1 | `(s a g,1,2)`、T=2 | priority は同点の中のタイブレークだけ(重み `weight` > priority の数) |
| FM13 | priority の数を数える | `make_network("s-a a-b b-g s-p p-q q-g s-x x-y y-g", types={"p": P, "x": P, "y": P})`、N=1 | `(s x y g,1,3)` | 同じ長さの3本(priority 0・1・2個)から、priority が一番多い経路 |
| FM14 | 押し戻し(back arc)で組み替える | `make_network("s-a a-b b-g s-c c-b a-d d-g")`、N=1 / N=2 | N=1: `(s a b g,1,3)`・T=3。N=2: `(s a d g,1,3)`, `(s c b g,1,3)`・T=3(a-b は使わない) | 2本目の最短路が a-b を逆にたどって打ち消す。`routes()` が打ち消した後の流れから正しく2本に分けること(負のコストの弧と Bellman-Ford を通る唯一の小さな例) |
| FM15 | start / end は無制限・end が restricted | `make_network("s-g", links={"s-g": 3})`、N=5 → `(s g,3,1)`・T=2。`make_network("s-g", types={"g": R})`、N=2 → `(s g,1,2)`・T=3 | start と end の容量の弧は `unlimited`(= N)。end へ入るコストも数える |
| FM16 | `max_drones` の無いハブ | `make_network("s-a a-g", links={"s-a": 5, "a-g": 5})` の a を `dataclasses.replace(zone, max_drones=None)` に差し替えた `Network`、N=4 / N=7 | N=4: `(s a g,4,2)`・T=2(rate は N で頭打ち)。N=7: `(s a g,5,2)`・T=3 | `Zone.capacity` が `None` のハブも無制限(=N)として扱う |

FlowGraph を直接使う補助のケース(FM 系の中に入れてよい。件数は上の 16 に含めず、作成フェーズで FM14 の下に置くか判断する):
- `FlowGraph(make_network("s-x x-g", types={"x": B}), 3).shortest_path()` は `None`、`routes()` は `()`。
- `FlowGraph(make_network("s-a a-g"), 3)`: 流す前の `routes()` は `()`。`shortest_path()` は3本の弧(s-a・a の中・a-g)、
  コストは `16, 0, 16`(weight = (3+1)×(3+1) = 16)、`turns` は `1, 0, 1`。`push(path, 1)` 後の `routes()` は
  `(Route(("s","a","g"),1,2),)`、次の `shortest_path()` は `None`。
- priority: `FlowGraph(make_network("s-a a-g s-p p-g", types={"p": P}), 2).shortest_path()` のコストは `14, 0, 15`(weight 15、p に入る弧だけ −1)。

#### 押さえた地図(HM。`flow_map.network`)

| ID | 対象 | 入力 | 期待値 | 理由 |
|---|---|---|---|---|
| HM01 | 使うゾーン・接続だけ | `make_network("s-a a-g s-b b-c c-g")`、N=1 | `zone_caps` = `{"s": None, "g": None, "a": 1}`、`link_caps` = `[("s-a",1), ("a-g",1)]` | b, c とその接続は落とす |
| HM02 | blocked は入らない | `make_network("s-x x-g s-a a-b b-g", types={"x": B})`、N=2 | routes `(s a b g,1,3)`・T=4。zone_caps `{"s":None,"g":None,"a":1,"b":1}`、接続 `[("s-a",1),("a-b",1),("b-g",1)]` | blocked のゾーンにはノードが無い |
| HM03 | 容量 = 1ターンに流す数 | 課題の例(`subject_map` を `load_world`)、N=5 | routes `(hub corridorA tunnelB goal,1,3)`, `(hub roof1 roof2 goal,1,4)`、T=5。zone_caps `{"hub":None,"goal":None,"roof1":1,"roof2":1,"corridorA":1,"tunnelB":1}`(obstacleX なし。corridorA は元の 2 → 1)、接続は6本すべて容量1(corridorA-tunnelB は元の 2 → 1) | 押さえた地図の容量は元の容量ではなく流れる数 |
| HM04 | 共有するゾーン・接続は合計 | FM05 の網、N=4 | zone_caps `{"s":None,"g":None,"a":1,"b":1,"m":2}`、link_caps `[("s-a",1),("s-b",1),("a-m",1),("b-m",1),("m-g",2)]` | 2本の rate を足す |
| HM05 | 宣言順と接続の名前を保つ | `make_network("a-s g-a")`(逆向きに宣言)、N=2 | link_caps `[("a-s",1), ("g-a",1)]`(経路は s→a→g の向き)、zone_caps のキーの順は `s, g, a` | 接続は `zone_a-zone_b` のまま(出力の接続名に使う)。並べ替えない |
| HM06 | ゾーンのほかの属性を保つ | 課題の例、N=5 | 押さえた地図の各ゾーンは元のゾーンと `max_drones` 以外が等しい(`replace(held_zone, max_drones=orig.max_drones) == orig`)。start/end は元のゾーンと等しい(`max_drones=None`) | 座標・色・型・役割を表示や resolver が使う |
| HM07 | 元の地図を変えない | `net = make_network("s-a a-g", capacity={"a": 3}, links={"s-a": 2})`、N=3 | 呼ぶ前後で `dict(net.zones)` と `tuple(net.connections)` が等しい、`net.get_zone("a").max_drones == 3`、`net.connections[0].max_link_capacity == 2`、`flow_map.network is not net`、押さえた地図の a は 1 | `replace` で新しいゾーンを作ること |
| HM08 | ドローン0 | `make_network("s-a a-g")`、N=0 | routes `()`、last_turn `0`、zone_caps `{"s": None, "g": None}`、接続なし | 経路が無いときは start と end だけ |

#### Pathfinder の構築と E2E(PF)

| ID | 対象 | 入力 | 期待値 | 理由 |
|---|---|---|---|---|
| PF01 | 到達不能(4パターン) | `"s-a b-g"`(離れている)、`"s-x x-g"` で x blocked、`""`(接続なし)、`"s-a a-g"` で g blocked | すべて `Pathfinder(net)` で `UnreachableGoalError`。`zone_name == "s"`、`goal_name == "g"`、メッセージ `goal 'g' is unreachable from 's'`(`line` を含まない) | 旧 P02 を引き継ぐ。構築時に失敗すること |
| PF02 | 孤立したゾーンは構わない | `make_network("s-a a-g", isolated=("z",))`、N=1 | 例外なし、routes `(s a g,1,2)`、押さえた地図に z は無い | 旧 P03 |
| PF03 | パーサー経由 | 課題の例をパース → `Pathfinder(world.network).flow_map(world.nb_drones)` | HM03 と同じ routes・T=5。到達不能なマップ(`nb_drones: 1` / `start_hub: s 0 0` / `end_hub: g 1 1` / `hub: a 2 2` / `connection: s-a`)はパースに成功し `Pathfinder` で `UnreachableGoalError` | 旧 E01・E02。到達可能かはパーサーではなく経路探索の仕事 |
| PF04 | 配布マップの1機の最短 | 配布マップ10枚と課題の例で `flow_map(1)` | last_turn(= routes[0].turns)は 課題の例 3、easy 3/3/3、medium 4/5/4、hard 6/5/12、challenger 19 | 旧 R08 の「1機の最短距離」の代わり(`distance` が無くなった)。R08 の下限にも使う |
| PF05 | 20×20 の格子 | `grid_network`、N=1 / 2 / 25 / 100 | N=1: routes 1本 `turns=38`、T=38。N=2: 2本(どちらも rate 1・turns 38)、T=38。N=25: 同じ2本、T=50。N=100: T=87。どれも 1 秒以内(実測 0.004 秒) | 大きめの網で止まらず速いこと。start の角の出口が2つなので2本で頭打ち |

### 2.2 `tests/simulation/scheduling/test_scheduler.py`(29 件)

#### `plan_departures`(PD)

`FlowMap(make_network(""), routes, T)` を直接作って渡す(`plan_departures` は `network` を見ない)。`summary` で比べる。

| ID | 対象 | 入力 | 期待値 | 理由 |
|---|---|---|---|---|
| PD01 | 1本・rate 1 | routes `(route("s a g",1,2),)`、T=3、N=2 | `{1: ("a",1), 2: ("a",2)}` | 1ターンに1席 |
| PD02 | 席の数 = rate × 出発できるターン数 | `(route("s a g",2,2),)`、T=3、N=4 / N=3 | N=4: `{1:("a",1),2:("a",1),3:("a",2),4:("a",2)}`。N=3: 最初の3席だけ | 出発ターンは `1 .. T − turns + 1` |
| PD03 | 到着の早い順 → 出発の早い順 | `(route("s a g",1,2), route("s r g",1,3))`、T=3、N=3 | `{1:("a",1), 2:("r",1), 3:("a",2)}` | D2 と D3 はどちらも到着3。出発1の r が、出発2の a より先 |
| PD04 | 同点は経路の番号順 | `(route("s a g",1,2), route("s b g",1,2))`、T=2、N=2 → `{1:("a",1),2:("b",1)}`。経路の順を入れ替えると `{1:("b",1),2:("a",1)}` | 名前ではなく `routes` の並び(=最短・priority の順)で決める |
| PD05 | T までに着けない経路には席がない | `(route("s a g",1,2), route("s r g",1,10))`、T=3、N=2 | `{1:("a",1), 2:("a",2)}` | `range(1, T − turns + 2)` が空 |
| PD06 | ドローン0 | routes `()`、T=0、N=0 | `{}` | |
| PD07 | 席が足りない | `(route("s a g",1,2),)`、T=2、N=2 → `SimulationError("the flow map has 1 seats for 2 drones")`。routes `()`、T=0、N=1 → `"the flow map has 0 seats for 1 drones"` | フローマップが間違っているときに黙って欠けない |
| PD08 | 課題の例 | `Pathfinder(subject).flow_map(5)` をそのまま | `{1:("corridorA",1), 2:("roof1",1), 3:("corridorA",2), 4:("roof1",2), 5:("corridorA",3)}` | D2・D4 が roof1 を回る(`scheduler_output` の元) |
| PD09 | `Departure` の値 | PD08 の D2 | `Departure(route=Route(("hub","roof1","roof2","goal"),1,4), turn=1)` と等しい。frozen(代入で `FrozenInstanceError`) | `Scheduler` が後で書き換えない |

#### `Scheduler`(SC)

| ID | 対象 | 入力 | 期待値 | 理由 |
|---|---|---|---|---|
| SC01 | `flow_map` は最初の判断まで `None` | `real_scheduler(make_network("s-a a-g"))` | 構築直後 `sch.flow_map is None`。`decide_moves(SimulationState(net, 2))` の後は routes `(s a g,1,2)`、last_turn `3` | 計画は最初のターンに作る |
| SC02 | 引く順(終点に近い順) | `make_network("s-a a-b b-g")`、3機を最後まで(resolver で進める) | 各ターンの指示 `[(1,"a")]`, `[(1,"b"),(2,"a")]`, `[(1,"g"),(2,"b"),(3,"a")]`, `[(2,"g"),(3,"b")]`, `[(3,"g")]` | 指示のリストの並びは「end に近いゾーンから」。ID 順ではない |
| SC03 | 課題の例の指示(順序ごと) | 課題の例を最後まで | `[(2,"roof1"),(1,"corridorA")]`, `[(1,"tunnelB"),(4,"roof1"),(3,"corridorA")]`, `[(1,"goal"),(2,"roof2"),(3,"tunnelB"),(5,"corridorA")]`, `[(2,"goal"),(3,"goal"),(4,"roof2"),(5,"tunnelB")]`, `[(4,"goal"),(5,"goal")]` | 引く順は goal, roof2, tunnelB, roof1, corridorA(残りターン数が同じなら押さえた地図の宣言順)。旧 R16 の置き換え |
| SC04 | start で出発を待つ | `make_network("s-a a-g")`、2機、ターン1 | `[MoveOrder(1, "a")]` だけ(D2 は出発ターン2なので指示なし) | 待つのは start の中だけ |
| SC05 | 飛行中には指示しない | `make_network("s-r r-g", types={"r": R})`、`place(net, 2, flying={1: ("s","r")})`、`turn_number = 1` | `[MoveOrder(2, "r")]`(D1 には指示しない。D2 は出発ターン2) | 着陸は resolver が自動で行う |
| SC06 | restricted への指示はゾーン名 | 同じ網を最後まで | 各ターンの指示 `[(1,"r")]`, `[(2,"r")]`, `[(1,"g")]`, `[(2,"g")]`。出力は `D1-s-r` / `D1-r D2-s-r` / `D1-g D2-r` / `D2-g` | 接続名にするのは resolver |
| SC07 | 配達済みには指示しない | `make_network("s-a a-g")`、2機を2ターン進めた後(D1 配達済み) | 3ターン目は `[MoveOrder(2, "g")]` | `active_drones` だけ見る |
| SC08 | 同じターンに2回呼ぶ | `make_network("s-a a-g")`、2機、ターン0の状態 | 2回とも `[MoveOrder(1,"a")]`。前後で `snapshot(state)` と各機の `history` が変わらない | 状態を読むだけ |
| SC09 | ターン0で計画し直す | 同じ `Scheduler` に `SimulationState(net, 2)` → `SimulationState(net, 3)`(どちらもターン0) | 2回目の後 `flow_map.last_turn == 4`(1回目は 3)、`flow_map` は別のオブジェクト | 新しい実行は台数が違っても作り直す |
| SC10 | ターン0以外では計画し直さない | `pathfinder.flow_map` を呼び出しを記録する関数で包み(`monkeypatch`)、2機を最後まで、毎ターン2回ずつ呼ぶ | 記録は `[2, 2]`(ターン0の2回だけ)。同じ `Scheduler` で2回目の実行をすると `[2, 2, 2]` | ターン0は呼ぶたびに作り直し、それ以降は作らない |
| SC11 | エラー: 出発のターンを過ぎた | `make_network("s-a a-g")`、`SimulationState(net, 2)` の `turn_number = 1`(全機 start のまま)、最初の呼び出し | `SimulationError("D1 missed its turn 1 to leave")` | 計画が守られていない |
| SC12 | エラー: 経路のない機 | 1機で計画(ターン0の状態で1回呼ぶ)した後、`place(net, 2, at={1: "a"})` の `turn_number = 1` を渡す | `SimulationError("D2 has no route")`(D1 は先に正しく引かれる) | 計画した台数と状態の台数が違う |
| SC13 | エラー: 経路から外れた | `make_network("s-a a-g s-b b-g")`(1機の経路は s a g)、`place(net, 1, at={1: "b"})`、`turn_number = 1` | `SimulationError("D1 is in 'b', off its route")` | `history` が経路の先頭と一致しない |
| SC14 | エラー: 経路の最後まで来たのに配達されていない | `make_network("s-a a-g")`、`place(net, 1, at={1: "a"})`、`turn_number = 1`、`state.drones[1].history.append("g")` | `SimulationError("D1 is in 'a', off its route")` | `step + 1 >= len(zones)` の側の分岐 |
| SC15 | エラー: いたゾーンに戻る | `net = make_network("s-a a-b a-g")`、`fixed_scheduler(net, FlowMap(net, (Route(("s","a","b","a","g"),1,4),), 4))`、`place(net, 1, at={1: "a"})` の後 `enter_zone(1, "b")`(history `["s","a","b"]`)、`turn_number = 2` | `SimulationError("D1 would go back into 'a'")` | 本物の経路は同じゾーンを2回通らないので、手で作った経路でしか起きない |
| SC16 | エラー: 押さえた地図に接続がない | `net = make_network("s-a a-g")`、`fixed_scheduler(net, FlowMap(make_network("s-a"), (route("s a g",1,2),), 2))`、`place(net, 1, at={1: "a"})`、`turn_number = 1` | `SimulationError("the flow map has no connection 'a'-'g'")` | |
| SC17 | エラー: 押さえた接続が満杯 | `net = make_network("s-a a-g", capacity={"a": 2}, links={"s-a": 2, "a-g": 2})`、`fixed_scheduler(net, FlowMap(make_network("s-a a-g", capacity={"a": 2}), (route("s a g",2,2),), 2))`、`SimulationState(net, 2)` | `SimulationError("D2: connection 's-a' of the flow map is full")` | 押さえた接続の容量 1 に2機 |
| SC18 | エラー: 押さえたゾーンが満杯 | 同じ `net`、押さえた地図 `make_network("s-a a-g", links={"s-a": 2, "a-g": 2})`(a は容量1)、`route("s a g",2,2)`、T=2、2機 | `SimulationError("D2: zone 'a' of the flow map is full")` | 接続の検査を通ってからゾーンの検査 |
| SC19 | エラー: 計画の席が足りない | 同じ `net`、押さえた地図は SC18 と同じ、`route("s a g",1,2)`、T=2、2機 | 最初の `decide_moves` が `SimulationError("the flow map has 1 seats for 2 drones")` | `plan_departures` のエラーがそのまま伝わる |
| SC20 | 指示が resolver に通る | 課題の例・restricted だけの例で毎ターン `TurnResolver.resolve` | 例外なしで完走し、ターン数は `flow_map.last_turn`(5 / 8) | 単体の範囲での結合確認(網羅は R03) |

### 2.3 `Drone.history`(7 件)

| ID | 置き場所 | 入力 | 期待値 | 理由 |
|---|---|---|---|---|
| DH01 | `tests/models/test_drone.py` | `Drone(1, "s")` と `Drone(2, "s")` | どちらも `history == []`、2つは別のリスト(`is not`) | `default_factory`。共有されると1機の記録が全機に混ざる |
| DH02 | `tests/simulation/test_state.py` | `SimulationState(make_network("s-a a-r r-g", types={"r": R}), 2)` | 全機 `["s"]`、別のリスト | start が最初 |
| DH03 | 同上 | D1 を `enter_zone(1, "a")` | D1 `["s","a"]`、D2 は `["s"]` のまま | 入ったゾーンを足す |
| DH04 | 同上 | 続けて `enter_transit(1, a-r, "r")` → `complete_transit(1)` | 飛行中は `["s","a"]`(足さない)、着陸後 `["s","a","r"]` | restricted は着陸したときに足す |
| DH05 | 同上 | 続けて `enter_zone(1, "g")` | `["s","a","r","g"]`、配達済み | end も足す |
| DH06 | 同上 | `make_network("s-g", types={"g": R})`、1機を `enter_transit` → `complete_transit` | `["s","g"]`、配達済み | restricted な end への着陸 |
| DH07 | 同上(resolver 経由) | `make_network("s-a a-g")` の2機に `[MoveOrder(1,"a"), MoveOrder(2,"a")]`(接続の容量違反) → 例外の後 `[MoveOrder(1,"a")]` | 違反のときは両機 `["s"]` のまま、次の正しいターンで D1 `["s","a"]`。restricted へは出発のターンに足さず、着陸のターンに足す(`s-r r-g` で `["s"]` → `["s","r"]`) | 不正なターンは何も変えない(履歴も) |

件数のまとめ: test_flow_map.py 36(LT 7・FM 16・HM 8・PF 5)、test_scheduler.py 29(PD 9・SC 20)、test_drone.py 1、test_state.py 6。

---

## 3. `test_scheduler_maps.py` の扱い(テストごと)

### 新しい `run_checked`(書き換え)

古い判定(`next_hops` / `detour_hops` / `distance` と、遠回りの回数)を捨て、次の不変条件にする。設計時に、課題の例・restricted だけの例・
配布マップ10枚・R15 の乱数マップ300枚・さらに広い乱数マップ約2000枚(blocked・priority・restricted な end・容量1〜4)で、すべて成り立つことを確認した。

1. 最初の `decide_moves` の後、`departures = plan_departures(scheduler.flow_map, nb_drones)` を作る(公開の関数。`Scheduler` 内部の計画と同じ値)。
2. 毎ターン: 1機1指示。指示は `AT_ZONE` の機だけ。
3. 指示の行き先は、その機の経路の次のゾーン(`departures[id].route.zones[len(drone.history)]`)で、`drone.history` に無い。
4. 待たない: start 以外にいる `AT_ZONE` の機は必ず指示を受ける。start の機は、出発ターン(`departures[id].turn`)に限って指示を受ける。
5. resolver がそのまま受理する。誰かが動く。既定の上限内。
6. 終わったとき: 各機の `history` は経路の `zones` と等しい。各機が配達されたターンは `route.arrival_turn(turn)`。全体のターン数は `flow_map.last_turn`。

戻り値は `CheckedRun(turns, routes_used)`(`routes_used` = 実際に使われた経路の数。遠回りの数の代わり)にする案。R15 の「何か1つは遠回り」の代わりに使う。

### テストごとの扱い

| ID | テスト | 扱い | 新しい期待値・理由 |
|---|---|---|---|
| R01 | `test_subject_sample_map_output` | **残す** | `scheduler_output` の5行と一致(確認済み) |
| R02 | `test_restricted_only_map_output` | **残す**(docstring だけ直す) | 8行は同じ。「立ち退かせる計画」の説明を「1本の経路に毎ターン1機」に |
| R03 | `test_every_turn_is_sound` | **直す** | 新しい `run_checked` を使う。docstring も新しい不変条件に |
| R04 | `test_provided_map_reaches_optimum` | **残す** | すでに通る。easy 4/4/4、medium 8/10/6、hard 13/16/26(すべて最適値ちょうど) |
| R05 | `test_challenger_within_quarter_of_optimum` | **直す** | 43 で最適値に届いたので、`<= optimum * 1.25` を `== optimum`(43)にし、R04 に入れてもよい(`GRADED_MAPS` の区別をやめる)。docstring の「44 turns (R19)」を消す |
| R06 | `test_provided_maps_archive` | **残す** | スケジューラに関係しない |
| R07 | `test_runs_are_deterministic` | **残す** | 通る |
| R08 | `test_turns_not_below_single_drone_bound` | **直す** | `Pathfinder.distance(start)` を `Pathfinder(net).flow_map(1).last_turn` に。値は PF04。課題の例 `== 5` の確認は残す |
| R09 | `test_single_restricted_zone` | **残す**(docstring を直す) | 4行は同じ。「old rules took 5」は残してよいが、計画の説明を変える |
| R10 | `test_wide_restricted_zone_with_narrow_exit`(K1・K2) | **直す** | 行数は同じだが行が変わる。K1(6行): `D1-s-r` / `D1-r D2-s-r` / `D1-g D2-r D3-s-r` / `D2-g D3-r D4-s-r` / `D3-g D4-r` / `D4-g`。K2(7行): `D1-s-r` / `D1-r D2-s-r` / `D1-a D2-r D3-s-r` / `D1-g D2-a D3-r D4-s-r` / `D2-g D3-a D4-r` / `D3-g D4-a` / `D4-g`。docstring「failed evictions are undone」を「出口の細さで1機/ターンに絞る」に。どちらも最適(時間展開の最大フローで確認) |
| R11 | `test_eviction_as_last_resort_map` | **直す** | 5行は同じ数、行が変わる: `D1-s-a D2-s-b` / `D1-a D2-b D3-s-a D4-s-b` / `D1-g D2-g D3-a D4-b D5-s-a D6-s-b` / `D3-g D4-g D5-a D6-b` / `D5-g D6-g`。立ち退きの話ではなくなったので名前を「restricted の2本」に変える |
| R12 | `test_restricted_zones_in_a_row` | **残す**(docstring を直す) | 3つとも行は同じ(two 6行・three 9行・normal-between 8行) |
| R13 | `test_rule_6_prime_map` | **直す** | 11行は同じ数。5行目以降が変わる(D3 は z2 を通らない。経路は `s z4 z3 z1 g` の1本): `D1-s-z4` / `D1-z4 D2-s-z4` / `D1-z4-z3 D2-z4 D3-s-z4` / `D1-z3 D2-z4-z3 D3-z4 D4-s-z4` / `D1-z1 D2-z3 D3-z4-z3 D4-z4 D5-s-z4` / `D1-g D2-z1 D3-z3 D4-z4-z3 D5-z4 D6-s-z4` / `D2-g D3-z1 D4-z3 D5-z4-z3 D6-z4` / `D3-g D4-z1 D5-z3 D6-z4-z3` / `D4-g D5-z1 D6-z3` / `D5-g D6-z1` / `D6-g`。規則6' は無くなったので名前を変える |
| R14 | `test_rule_7_map` | **残す**(名前と docstring を直す) | 8行は同じ。規則7 は無くなった |
| R15 | `test_random_restricted_maps_never_get_stuck` | **直す** | 新しい `run_checked` で300枚(`random.Random(2026)` のまま)。`assert detours >= 1` を「2本以上の経路を使うマップが少なくとも1枚」に(実測 52 枚) |
| R16 | `test_subject_sample_map_orders` | **直す**(SC03 と同じ値) | 指示の順が変わる。SC03 と重なるので、こちらを消して SC03 だけにしてもよい(「確認したい点」2) |
| R17 | `test_priority_puzzle_output` | **残す**(docstring を直す) | 6行は同じ。説明を「2本の経路(4ターン・5ターン)」に |
| R18 | `test_small_detour_map` | **直す** | two: `D1-a` / `D1-g D2-a` / `D2-g`(r を使わない。FM09)。three: 同じ3行。four: `D1-a D2-s-r` / `D1-g D2-r D3-a D4-s-r` / `D2-g D3-g D4-r` / `D4-g`(4行は同じ数) |
| R19 | `test_provided_map_turn_counts` | **直す** | `PROVIDED_TURNS` の challenger を 44 → 43。すべて最適値と等しくなるので、R04 と表を1つにまとめられる(「確認したい点」3) |
| R20 | `test_detours_taken_on_real_maps` | **捨てる**(または置き換え) | 遠回りという考えが無くなった。置き換えるなら「使う経路の数」(`len(flow_map.routes)`)を固定する: 課題の例 2、easy 1/2/1、medium 1/1/2、hard 1/1/1、challenger 1 |
| — | `orders_by_turn` ヘルパー | 残す | R16(または SC03)で使う |
| — | `CheckedRun.detours` | 捨てる | `routes_used` に置き換え |
| — | モジュールの docstring | 直す | 「Stage 5 Scheduler」をフローマップの説明に |

参考: R13 / K1 / K2 / R11 / R18(4機)のターン数は、待つことも許した時間展開の最大フロー(scratchpad の検算)の最小ターン数と等しい。

---

## 4. `tests/README.md` の更新

削除したファイル・クラスを書いている行(行番号は今の `tests/README.md`):

| 行 | 今の内容 | 直し方 |
|---|---|---|
| 11〜12 | 例として `scheduler_reservation_table.py` の `Evictor` → `test_evictor.py` | 今ある例に替える(例: `pathfinder.py` の `FlowMap` → `tests/pathfinding/test_flow_map.py`) |
| 30 | `test_drone.py` の説明 | `Drone.history`(既定は空のリスト・機ごとに別)を足す(DH01) |
| 111〜113 | `test_distance_map.py`(`DistanceMap`) | 削除 |
| 114〜123 | `test_pathfinder.py`(`distance` / `next_hops` / `detour_hops` / `route_cost`) | 削除し、`test_flow_map.py`(LT / FM / HM / PF)の説明に置き換え |
| 124〜131 | `test_detour_policy.py` | 削除 |
| 132〜140 | `tests/simulation/conftest.py` | `FollowerScheduler` を「1機のフローマップの最速の経路をたどる」に。`hop` / `evictor_for` / `moves_of` / `taker_for` を削除(もう無い)。`fixed_scheduler` を追加 |
| 141〜144 | `test_state.py` | `history`(DH02〜DH07)を足す |
| 160 | `test_engine.py` の「貪欲なスタブ `FollowerScheduler`」 | そのままでよい(12行は今も通る) |
| 162〜170 | `test_turn_ledger.py` | 削除 |
| 171〜176 | `test_reservation_table.py` | 削除 |
| 177〜180 | `test_evictor.py` | 削除 |
| 181〜196 | `test_scheduler.py`(古い判断の順序・遠回り・予約と立ち退き) | 新しい `test_scheduler.py`(PD / SC)の説明に置き換え |
| 197〜213 | `test_scheduler_maps.py` | 新しい不変条件・配布マップのターン数(すべて最適値)・使う経路の数(R20 を残す場合)に書き換え。「challenger は最適値43の25%以内。最適値そのものには届かない」「遠回り」「予約表と立ち退きの E2E」「規則6'・規則7」を消す |
| 219〜222 | `test_positions.py` | 削除 |
| 227〜230 | `test_hop_taker.py` | 削除 |
| 231〜236 | `test_zone_ranking.py` | 削除 |

`tests/conftest.py` の `SCHEDULER_OUTPUT` のコメント(「two drones go round by roof1」)は今も正しい(D2・D4 が roof1 の経路)。

---

## 5. 確認中に気づいたこと

- **不具合は見つからなかった**。上の乱数マップ(R15 の300枚・広い乱数約2000枚)で、`SimulationError` も resolver の違反も起きず、
  不変条件 1〜6 がすべて成り立った。小さな乱数マップ322枚では、`flow_map.last_turn` が「待つことも許した時間展開の最大フロー」の
  最小ターン数と一致した(最適)。
- **小さな気づき(壊れた状態を見逃す)**: `history` が空の機(`Drone` を直接作ると既定で `[]`)は、`scheduler.py:213-221` で
  `step = -1` になり、`zones[:0] == ()` が一致してしまうので「経路の0番目(start)へ引く」扱いになる。start は引く順(`_pull_order`)に
  入っていないので、エラーにならず**黙って指示が出ない**。再現: `make_network("s-a a-g")`、`place(net, 1, at={1: "a"})`、
  `turn_number = 1`、`state.drones[1].history.clear()` → `decide_moves` は `[]`(「off its route」にならない)。
  `SimulationState` は必ず `[start]` を入れるので、通常の実行では起きない。課題と Linux の範囲に絞る方針から、直さずテストもしない案を推す
  (直すなら `step < 0` も off route に含める)。
- `decide_moves` はターン0では呼ぶたびに `Pathfinder.flow_map` を呼び直す(SC10 で `[2, 2]`)。docstring どおりで不具合ではない。
- `FlowMap` 同士は `==` で比べられない(`Network` に `__eq__` が無い)。テストでは中身を比べる(方針に記載)。

## 確認したい点

1. `take_snapshot`(`tests/conftest.py`)に各機の `history` を足すか。足すと DH07・SC08 が `snapshot` だけで済むが、既存の
   snapshot の比較すべてに効く(どれも履歴を変えない操作なので通るはず)。
2. R16 と SC03 は同じ値。E2E 側(R16)を消して SC03 だけにするか、両方残すか。
3. R04・R05・R19 を「配布マップ10枚のターン数 = 最適値」の1つのテストにまとめるか(すべて最適値と等しくなったため)。
4. R20 を捨てるか、「使う経路の数」の固定に置き換えるか。
