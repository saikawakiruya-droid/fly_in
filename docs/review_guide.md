# レビュー対策: Fly-in の全体像

- 作成: 2026-10-22(develop a58ac33 時点のコードから)
- 目的: ピアレビューで「何をどう作ったか」を自分の言葉で説明できるようにする。README(提出物)の要約ではなく、
  **説明の順番・聞かれそうなこと・根拠の場所**をまとめたもの。
- 詳しい根拠: `docs/decisions.md`(なぜそうしたか)、`docs/bugs.md`(何が起きたか)、`docs/archify/`(図)。

---

## 1. 30秒で説明するなら

> マップを読んで検査し、**ゴールから逆向きに1回だけ Dijkstra** をして全ゾーンの「ゴールまでの最短ターン数」を出します。
> 毎ターン、**スケジューラ**がその距離を見て各ドローンの一手を決め(空きがなければ先にいる機を押し出す・遠回りする・待つ)、
> **TurnResolver** がそのターン全体をルールに照らして検査してから反映します。反映されたターンを**オブザーバ**が
> 標準出力(ターンログ)・表示・記録に流します。グラフ系ライブラリは使わず、グラフも探索もスケジューラも自作です。

キーワード3つ: **「距離は1回だけ計算」「決める人(Scheduler)と検査する人(TurnResolver)を分けた」「出力はオブザーバ」**。

---

## 2. 処理の流れ

### 2.1 起動から終了まで

```text
fly_in.py  main()               引数 → 終了コード、例外 → "error: ..." の1行
  └ Application.run()           (app.py) 各段階をつなぐだけ
      ① 読み込み   MapParser.parse()          → World(Network + nb_drones)
                   (--from-world なら WorldFile.read())
      ② 距離       Pathfinder(network)        → DistanceMap(ゴールから Dijkstra)
                                                到達できなければ UnreachableGoalError
      ③ シミュ     SimulationEngine.run(observers)
                     毎ターン: Scheduler.decide_moves() → TurnResolver.resolve()
      ④ 出力       ObserverGroup: TurnLogPrinter(stdout) / 表示 / RunRecorder
                   最後に RunSummary(stderr に1行)
```

### 2.2 1ターンの中身

```text
SimulationEngine._play_turn()
  1. ターン数が上限(2 × ゾーン数 × ドローン数)を超えていたら SimulationError
  2. orders = Scheduler.decide_moves(state)        ← 「どこへ行くか」を決める(MoveOrder のリスト)
  3. moves  = TurnResolver.resolve(state, orders)  ← 「それは合法か」を検査して反映(Move のリスト)
  4. moves が空なら SimulationError(誰も動かない = 永久に進まない)
  5. observer.render(state, moves)                 ← 1行出力・描画・記録
```

`MoveOrder`(スケジューラの指示: 「D3 を roof1 へ」)と `Move`(出力される結果: `D3-hub-roof1`)を
**別の型にしている**のがポイント。スケジューラは結果を作れない。

---

## 3. パッケージ地図(どこに何があるか)

| パッケージ | 主なクラス | 一言で |
|---|---|---|
| `fly_in.py` | `main` | 入口。終了コード(0/1/2/130)と、想定外の例外を1行にする最後の砦 |
| `droneflow/cli.py` | `Args`, `parse_args` | argparse の結果を型付きの `Args` にする |
| `droneflow/app.py` | `Application` | 各段階を組み立てるだけ。ロジックは持たない |
| `droneflow/errors.py` | `FlyInError` と子 | 想定内の失敗はすべてこの子クラス → `error: ...` |
| `models/` | `Zone`, `ZoneType`, `Connection`, `Drone`, `Network`, `World` | 土台。`Network` が自作のグラフ(ゾーンの辞書 + 隣接リスト) |
| `parsing/` | `MapReader` → `LineTokenizer` → `MapValidator` (+ `Rule`) | 読む・分ける・検査する、を委譲で分割。行の仕様は `MapFormat` の表 |
| `pathfinding/` | `DistanceMap`, `Pathfinder`, `Hop` | 距離と「次の一手」の候補。容量は見ない |
| `simulation/` | `SimulationEngine`, `TurnResolver`, `SimulationState`, `TurnObserver` | ターンのループとルール検査 |
| `simulation/scheduling/` | `Scheduler` と部品7つ | 毎ターンの判断(下の 4.4〜4.7) |
| `output/` | `TurnLogPrinter`, `TurnLogFormatter`, `RunSummary` | stdout のターンログと stderr の要約 |
| `visualization/` | `TerminalVisualizer`, `GraphicalVisualizer` | 表示。pygame を import するのは `graphical_view.py` だけ(遅延 import) |
| `interchange/` | `WorldFile`, `RunRecorder` | 追加機能の JSON(`--parse-only` / `--from-world` / `--save-run`) |

### スケジューラの部品(`simulation/scheduling/`)

| クラス | 役割 |
|---|---|
| `Scheduler` | 司令塔。判断の順に各ドローンへ「一手」を探させる |
| `ZoneRanking` | どのゾーンのドローンから判断するか(順位を1回だけ計算) |
| `TurnLedger` | このターン・この先のターンの「空き」を数える台帳 |
| `HopTaker` | 候補の一手を順に試し、最初に通るものを採る(押し出しなし → あり) |
| `Evictor` | 満杯のゾーンにいる機を「何ターン目に先へ進む」と予約して席を空ける |
| `ReservationTable` | 予約(着陸・押し出し)の表。`mark` / `rollback` で失敗した試みを消せる |
| `DetourPolicy` | 最短の一手がとれない機に、遠回りを許すかどうか |
| `PositionBoard` | このターンに決めた分を反映した「各機の居場所」 |

---

## 4. 説明できるようにしておく仕組み

### 4.1 パーサ(評価シート「パーサーの実装」)

- `MapReader` が行番号付きで1行ずつ渡す → `LineTokenizer` が `MapFormat`(行の種類・フィールド・既定値・変換関数の表)で構文を検査して分割
  → `MapValidator` が値を変換し、複数行にまたがる検査を `Rule` の列に任せる。
- `Rule`: `UniqueZoneName`, `SingleStartAndEnd`, `KnownEndpoints`, `UniqueConnection`([map_rules.py](../droneflow/parsing/map_rules.py))。
  ここだけ継承(`ZoneRule` / `ConnectionRule` の ABC)を使っている。全体は委譲。
- **最初のエラーで止まり、行番号と理由を出す**。例: `error: line 4: unknown zone: x`。
- 決めたこと(聞かれやすい):
  - 1行目は**物理的な1行目**が `nb_drones:`(課題文「The first line must define…」)。配布マップは先頭がコメントなので、
    README の `sed -n '/^nb_drones:/,$p'` で前を削って渡す。
  - `a-b` と `b-a` は同じ接続 → 重複エラー。ゾーン名に `-` は不可(出力の `zone_a-zone_b` が曖昧になる)。
  - メタデータのキー重複はエラー(後勝ちにすると start の `zone=blocked` が隠れるため。bugs.md 2026-10-16)。
  - start/end の `max_drones` は受け付けて無視、`zone=blocked` はエラー。
  - 行末の `#` コメントはエラー、先頭の BOM は読み飛ばす。

### 4.2 距離: ゴールから1回だけの Dijkstra([distance_map.py:41](../droneflow/pathfinding/distance_map.py#L41))

- **逆向き**にする理由: 知りたいのは「各ゾーンからゴールまで」。ゴールから1回探索すれば全ゾーンぶん同時に出る。
  ドローンごと・ターンごとに探索し直さない。
- コスト = **入るゾーンの** `turn_cost`(normal/priority 1、restricted 2)。だから逆向きでは「`u` に入るコストを、隣 `w` の距離に足す」。
- blocked は距離を持たない(入らない・通らない)。
- **容量は無視**: 容量はターンごとに変わるのでスケジューラの仕事。距離は地形だけで決まる不変量。
- 到達不能はここで分かる: start の距離が `None` → `UnreachableGoalError`(`Pathfinder` の構築時)。
- 計算量: O((Z + C) log Z) を1回だけ。`heapq` は標準ライブラリなので禁止に当たらない。

### 4.3 次の一手([pathfinder.py:58](../droneflow/pathfinding/pathfinder.py#L58))

- `next_hops(u)`: 隣 `v` で `turn_cost(v) + dist(v) == dist(u)` のもの = 最短経路を外れない一手。**priority を先**、あとは宣言順。
- `detour_hops(u)`: 隣 `v` で、ゴールに届くが合計が `dist(u)` より大きいもの。コストの小さい順。
- priority は「同じ長さの中で優先」するだけ。長い priority 経路は選ばない(課題: 同じ長さなら priority)。

### 4.4 スケジューラの1ターン([scheduler.py:92](../droneflow/simulation/scheduling/scheduler.py#L92))

1. restricted へ飛行中の機には命令しない(次のターンに必ず着地する。着地は `TurnResolver` が自動で行う)。
2. 予約表で「このターンに動く」と決まっている移動を先に命令する。
3. 残りの機を `ZoneRanking` の順に判断する:
   **ゴールに近いゾーンから** → priority 経路上 → 出口が少ない → 宣言順。
   - 近い順の理由: 前の機が出ていく分を台帳に載せてから後ろの機を判断できる。課題の例で 11 → 7 ターンになった(stage5-benchmark)。
   - 出口が少ない順の理由: 選択肢のある機が、出口が1つしかない機の唯一の出口をふさがない。
4. 各機は `HopTaker.take_first` で、最短の一手を **押し出しなし → 押し出しあり** で試す。だめなら遠回りを同じ2段階で。全部だめなら待機(命令なし)。

### 4.5 空きの数え方(`TurnLedger` と `TurnResolver` で同じ規則)

- **ゾーン**: 同じターンに出ていく機が、入る機のために席を空ける(最終人数で判定)。
  restricted へ向かった機は、**着地したターンから**そのゾーンに数える(出発したターンは接続の上)。
- **接続**: 出発したターンだけ容量を使う。向きは区別しない。restricted への着地のターンは接続容量に数えない
  (decisions 2026-10-18「restricted の到着ターンは接続容量に数えない」)。
- start / end は容量無制限。
- 台帳は「今いる数 + 予約・決定済みの入り − 出」で、**この先のターンの見込み(projected load)**まで数える。
  後で予約された機のために席を残しておくため。

### 4.6 押し出し(Evictor)と予約表

- 問題: restricted へは「出発したら次のターンに必ず着地」。着地先が満杯だと接続の上で詰まる(ルール違反)。
- 解決: 出発の時点で、着地のターンに席があることを確かめる。満杯なら、中にいる機に「そのターンに最短の一手で先へ進む」予約を入れる
  (その先も満杯なら再帰)。予約は `ReservationTable` に入り、次のターンに 4.4 の 2 で命令される。
- 必ず終わる理由: 押し出し1回ごとにゴールまでの距離が真に減る。ゴールは容量無制限。
- 失敗した試みは `mark` / `rollback` で跡を残さない。
- 押し出しは**最後の手段**(まず押し出しなしで全候補を試す)。

### 4.7 遠回り(DetourPolicy、[detour_policy.py:86](../droneflow/simulation/scheduling/detour_policy.py#L86))

- 最短の一手がどれも取れない機だけが試す。条件:

  ```text
  turn_cost(v) + dist(v) + queue(v)  <=  dist(u) + ahead(u)
  ```

  - `ahead(u)`: 最短経路の先にいる機の数(先に通す必要がある数)。
  - `queue(v)`: 遠回り先 `v` とその先にいる機の数。
  - 意味: 「並んで待つより遅くならない見込みなら遠回りしてよい」。
- 逆流の防止: **一度いたゾーンには遠回りで入らない**。
- 効果: 課題の例 7 → 5、priority_puzzle 8 → 6、circular_loop 15 → 10。

### 4.8 必ず終わる(停止性)

- 各機の移動は有限: 最短の一手は距離を真に減らし、遠回りは「まだいたことのないゾーン」にしか入らない。
- 毎ターン少なくとも1機は動く: 予約と着地は必ず起きる。それ以外でも、ゴールに一番近い機は最短経路に必ず空きがある(ゴールは無制限)。
- それでも保険として、エンジンは「誰も動かないターン」と「上限ターン数」で止まる([engine.py:20](../droneflow/simulation/engine.py#L20))。

### 4.9 ルール検査(TurnResolver、[turn_resolver.py:56](../droneflow/simulation/turn_resolver.py#L56))

1. 飛行中の機を着地させる。
2. 各命令を検査: 存在する・未配送・飛行中でない・1機1命令・存在して blocked でない・隣接・今いるゾーン以外。
3. 接続容量(出発する機だけ数える)。
4. ゾーン容量(最終人数で。着地できない機は「接続上で詰まった」と報告)。
5. **ターン全体が合法なときだけ**状態を変える。

→ 「スケジューラを信用していない。出力されたターンはすべて検査済み」と言える。スケジューラのバグは不正なログではなく `SimulationError` になる。

### 4.10 出力

- stdout には**ターンログだけ**。1ターン1行、ドローン番号順、動かない機・配送済みの機は書かない。
- restricted へ出発したターンは `D2-hub-roof1`(接続名は宣言どおり)、着地のターンは `D2-roof1`。
- 表示・警告・エラー・要約は stderr。`2>/dev/null` で求められた出力だけになる。
- `TurnLogPrinter` は1行ごとに flush。`| head` で閉じられてもトレースバックを出さない(`fly_in.py` の `BrokenPipeError`)。

---

## 5. 設計の「なぜ」(聞かれたら)

| 質問 | 答え | 根拠 |
|---|---|---|
| なぜ BFS でなく Dijkstra? | restricted が2ターンでコストが均一でないから。 | decisions 2026-10-03 |
| なぜ距離を毎ターン計算し直さない? | 距離は地形だけで決まり変わらない。混雑はスケジューラが台帳で扱う。 | 同上 |
| なぜ決定と検査を分けた? | スケジューラが複雑なので、間違えても不正な出力を出さないため。テストで別の決定器も差し込める(`Application` の `make_scheduler`)。 | decisions 2026-10-16「Stage 4 の API」 |
| なぜオブザーバ? | ターンログ・ターミナル表示・グラフィカル表示・記録が全部同じ「毎ターン呼ばれる口」で済む。追加も1行(ライブコーディングもここ)。 | decisions 2026-10-18 |
| 継承は使っている? | ほぼ委譲。`Protocol`(`MoveDecider`, `TurnObserver`, `Rule`)で接合部を決めている。`map_rules.py` だけ ABC の継承。 | decisions 2026-10-21 の 6 |
| なぜ全体最適(フロー等)にしない? | 最小カットの試作はしたが、実行で使われなかったので取り下げた。代わりに局所的なルール(押し出し・遠回り・判断順)で目標を満たした。 | decisions 2026-10-19, 2026-10-21 の 1 |
| ターン上限はなぜ `2 × Z × D`? | 1機ずつ送れば必ず終わり、それは1ゾーンあたり約2ターン。証明された上限ではなく暴走検知の保険。 | engine.py の docstring |
| pygame がなくても動く? | 動く。import は `graphical_view.py` だけで遅延。`--visual terminal/none` なら不要。 | README |
| グラフ系ライブラリは? | 不使用。`Network` は辞書と隣接リストの自作、探索は `heapq` だけ。 | — |

---

## 6. 評価シートとの対応とデモ

評価シートの項目は `docs/research/2026-10-16_review-test-patterns.md`、テスト用マップは `revie_case/maps/`(ローカル。リポジトリ外)。

| 評価項目 | 見せ方 |
|---|---|
| パーサー・エラー処理 | `revie_case` の E01〜E40 を実行 → すべて `error: line N: ...` の1行、終了コード 1 |
| 非連結・到達不能 | X02 / X03 / X05 → パースは通り、`error: goal 'e' is unreachable from 's'` |
| 区域占有・移動コスト・接続容量 | 課題の例をターミナル表示で `--step`。`roof1 R 1/1+1*`(出る機と入る機が同じターン)を説明 |
| 出力形式・静止ドローンの省略 | `make run ARGS="--visual none"`、`2>/dev/null` で stdout だけ見せる |
| 紛争解決 | 4.4〜4.7。違反があれば `TurnResolver` が止めるので「完走 = 違反なし」 |
| パフォーマンス | X11(25×25 グリッド)71ターン、X08(多数の機・狭い経路)201ターン。距離計算は1回 |
| 静的検査 | `make lint`、`make lint-strict` |

### ベンチマーク(2026-10-22、WSL)

| マップ | ターン | 目標 |
|---|---|---|
| easy: linear_path / simple_fork / basic_capacity | 4 / 4 / 4 | 6 / 8 / 6 |
| medium: dead_end_trap / circular_loop / priority_puzzle | 8 / 10 / 6 | 12 / 15 / 12 |
| hard: maze_nightmare / capacity_hell / ultimate_challenge | 13 / 16 / 26 | 30 / 35 / 45 |
| challenger: the_impossible_dream | 44 | 45 未満(ボーナス) |
| 課題の例 | 5 | — |

出典: `docs/research/2026-10-22_wsl-full-partial-runs.md`。

### デモの手順(例)

```sh
make install
make run                                   # 課題の例、ターミナル表示
make run ARGS="--visual none" 2>/dev/null  # ターンログだけ
make run ARGS="--visual graphical --step"  # 右矢印で1ターンずつ
sed -n '/^nb_drones:/,$p' maps/hard/03_ultimate_challenge.txt > /tmp/m.txt
make run MAP=/tmp/m.txt ARGS="--visual none"
make lint && make lint-strict
```

(配布マップのパスは展開した場所に合わせる。)

---

## 7. 正直に言っておく制約・既知の問題

- **1行目がコメントのマップは拒否する**(仕様として決めた)。配布マップは README の手順で前を削る。評価者が驚かないよう、最初に言っておく。
- 最適解ではない: 局所的なルールの組み合わせなので、マップによっては下限より多い(challenger 44 は参考記録 45 未満だが下限 19 + α より多い)。
- 同じゾーン内の機の並びは ID 順で、遠回りの判断が機ごとに違うため結果に影響しうる(decisions 2026-10-20 の追記)。
- VG08(グラフィカル表示のテスト)が WSL でときどき失敗する。コードの問題ではなくテスト環境側と見ているが未調査(bugs.md 2026-10-22)。
- Makefile は Linux 前提(`.venv/bin/python`)。Windows 対応は外した(decisions 2026-10-22)。

---

## 8. ライブコーディング(`--capacity-info`)

手順と編集する箇所は `docs/research/2026-10-22_live-coding-capacity-info.md`。答えのコードは書いていない(本番で自分で書く)。
要点だけ:

- 足す場所は3か所: `cli.py`(フラグ)、新しいオブザーバ、`app.py` の `observers`。
- 出力は **stderr**(stdout はターンログだけ)。`--visual none` でも出るよう、views ではなく observers に足す。
- 接続の使用数は、そのターンの `moves` の `connection_name` を数える(着地は `None` なので自然に規則と一致する)。

---

## 9. 用語の対応

| 課題の言葉 | コードの名前 |
|---|---|
| zone / hub | `Zone`(種別 `ZoneType`、役割 `ZoneRole`) |
| connection | `Connection`(名前は宣言どおりの `a-b`) |
| max_drones | `Zone.capacity`(start/end は `None` = 無制限) |
| max_link_capacity | `Connection.max_link_capacity` |
| 1ターンの移動 | 指示は `MoveOrder`、結果は `Move` |
| 最短の一手 / 遠回り | `Pathfinder.next_hops` / `detour_hops`(`Hop`) |
| 予約 | `Reservation`(着地・押し出し) |

---

## 10. 当日までに自分で確認しておくこと(チェックリスト)

- [ ] 1章の30秒説明を何も見ずに言える
- [ ] 課題の例の5ターンを、なぜその動きになるか1行ずつ説明できる(D2 が `hub-roof1` に出る理由など)
- [ ] 「restricted の着地先が満杯ならどうする?」に押し出しで答えられる
- [ ] 遠回りの不等式の各項を説明できる
- [ ] 「必ず終わるのはなぜ?」に 4.8 で答えられる
- [ ] `--capacity-info` を10分以内で書く練習をした(`feature/capacity_info` から切ったブランチで)
- [ ] 評価環境で `make install` → `make run` → `make lint` が通るのを確認した
