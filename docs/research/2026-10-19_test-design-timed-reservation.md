# テスト設計: 予約表と立ち退き(timed reservation)

- 日付: 2026-10-19
- フェーズ: **テスト設計**(テストコードは書いていない)
- 対象ブランチ: `test/timed_reservation`(`feature/timed_reservation` から分岐)
- 対象コード: `droneflow/simulation/reservation_table.py`(`Reservation` / `ReservationTable` / `landings`)、
  `droneflow/simulation/evictor.py`(`Evictor`)、`droneflow/simulation/turn_ledger.py`(追加された `link_free` / `has_seat(s)` /
  `projected` / `horizon` / `arrival_turn` / `cancel`)、`droneflow/simulation/turn_resolver.py`(着陸を最終負荷に数える・
  restricted への出発を出発のターンに数えない・「接続上で詰まった」)、`droneflow/simulation/scheduler.py`(予約した移動を先に・
  最後の手段の立ち退き・規則6'・規則7・同じターンの再呼び出し)。`state.py` / `engine.py` は変更なし(読むだけ。E2E で使う)。
- 参照した決定: `docs/decisions.md`
  - 2026-10-18「restricted の到着ターンは接続容量に数えない」(以下 **到着接続**)
  - 2026-10-18「restricted の予約は、着陸ターンごとの予約表で数える」(以下 **予約表**)
  - 2026-10-18「restricted へ出発する席がなければ、在室機を立ち退かせ…」(以下 **立ち退き**。規則番号は設計案 2 章の 1〜9)
  - 2026-10-18「Q-A・Q-B・Q-C の決定」(以下 **Q-A** / **Q-B** / **Q-C**。Q-C = 最後の手段)
  - 2026-10-18「ふつうの移動は…自分の立ち退きを予約して入る(規則6')」(以下 **規則6'**)
  - 2026-10-19「予約表と立ち退きの実装で決めた細部」(以下 **細部1〜7**)
  - 2026-10-17「Stage 5 の API」ほか、`2026-10-17_test-design-stage5-scheduler.md` の作成フェーズの申し送り(R04 は VII.7 の目標値で検査)
- 参照した資料: `docs/research/2026-10-18_design-timed-reservation.md`(以下 **設計案**)、
  `docs/research/2026-10-18_last-resort-eviction.md`(以下 **最後の手段の報告**)、`docs/research/2026-10-17_stage5-benchmark.md`
  (2026-10-19 追記)、`docs/research/2026-10-16_workflow-stage4-simulation.md` / `2026-10-17_workflow-stage5-scheduler.md`(2026-10-19 更新)
- 参照したバグ記録: `docs/bugs.md`(この変更に関係する既知のバグはなし)。**設計中に1件見つけて追記した**(下記「バグ」)。
- 書式の手本: `docs/research/2026-10-17_test-design-stage5-scheduler.md`

## 方針

- 構成は今のまま(`tests/simulation/` に対応するファイルを置く)。新しいファイルは `test_reservation_table.py`(Q 系)と
  `test_evictor.py`(X 系)の2つ。ほかは既存ファイルに追記する。
- 単体テストのネットワークはテストコード内で組む(`make_network`)。ドローンの配置は `place`(検査をしない基本操作)。
  ターン番号が要るときは `state.turn_number` を直接書き換えてよい(公開属性。準備のための操作)。
- 予約表の中身を見るときは `ReservationTable` の公開メソッド(`planned` / `entering` / `leaving` / `due` / `last_turn` / `mark`)だけを使う。
  **`Scheduler` の非公開属性(`_table` など)は読まない**。スケジューラの予約は、`decide_moves` の戻り値と、その後のターンの指示・出力で観察する。
- E2E は `make_network` か、`write_map` / `load_world`(tmp_path)で組む。**`revie_case/` と scratchpad には依存しない**
  (S07・K1・K2 は設計案に書かれた構成をテストの中に書く)。
- 下表の期待値は、設計時に `feature/timed_reservation` の実装でアドホックに実行して一致を確かめた(scratchpad、コミットしない)。
- `tests/README.md` のカバレッジ欄への追記は作成フェーズで行う。

## ファイル構成

```
tests/
└── simulation/
    ├── conftest.py                  # 追記: evictor_for(下記)
    ├── test_reservation_table.py    # 新規: Q01〜Q10
    ├── test_evictor.py              # 新規: X01〜X09
    ├── test_turn_ledger.py          # 更新: L08・L09 / 追記: L13〜L21
    ├── test_turn_resolver.py        # 更新: T13・T14・T21d(+T21e)/ 追記: T25〜T30
    ├── test_scheduler.py            # 更新: D12 / 追記: D18〜D25
    ├── test_engine.py               # 追記: G12
    └── test_scheduler_maps.py       # 更新: R02 / 追記: R09〜R15
tests/visualization/test_graphical_view.py   # 更新: VG06[restricted_only]
```

- ID の接頭辞: 新しく `Q` = 予約表(ReservationTable)、`X` = 立ち退き(Evictor)。既存の `L` / `T` / `D` / `G` / `R` は続き番号。
  `Q` と `X` は既存のテストで使われていない(`grep` で確認)。

## 共有ヘルパー(`tests/simulation/conftest.py` に追記)

| 名前 | 中身 | 使うケース |
|---|---|---|
| `evictor_for(state, table=None) -> tuple[ReservationTable, TurnLedger, Evictor]` | `table` がなければ新しく作り、`table.start_turn(state)` してから `TurnLedger(state, table)` を作る。`hops = {z: Pathfinder(network).next_hops(z) for z in network.zones}`、`positions` は `Scheduler._positions` と同じ規則(着陸する機は `(transit_target, turn_number + 1)`、ゾーンにいる機は `(current_zone, turn_number)`、配達済みは含めない)で作り、`Evictor(ledger, hops, positions)` を返す | X 系 |

- `positions` の作り方は `Scheduler._positions`(非公開)の複製になる。テストから非公開メソッドを呼ばないための複製で、
  docstring に「Scheduler._positions と同じ規則」と書く(確認したい点 3)。
- 予約を足した台帳は `t = ReservationTable(); t.start_turn(state); t.reserve(...); TurnLedger(state, t)` の形で作る(L 系)。
  `start_turn` の**後に** `reserve` する(`start_turn` は出発元にいない機の予約を捨てるため、順序で結果が変わる)。

## A. 既存テストの更新(8件。いずれも設計どおりの期待の変化)

| テスト | 今の期待 | 新しい期待 | 理由(決定) |
|---|---|---|---|
| `test_scheduler.py::test_no_order_for_drone_in_flight`(D12) | `[]`(D2 は s-r が着陸する D1 で使用中なので待機) | `[O(2,"r")]`。D1 には指示しない(名前の意味は保つ)。docstring を「D1 は飛行中なので指示なし。着陸で s-r が空くので D2 は出発する」に | 到着接続(着陸のターンは接続を使わない)。r は容量2で、ターン2の r = 着陸して残る D1 + D2 = 2 ≤ 2(予約表・規則3) |
| `test_turn_ledger.py::test_drone_in_flight_uses_its_link`(L08) | `has_room(hop(s,r))` が False | **True**。名前を `test_landing_drone_frees_its_link` に、docstring を「着陸する D1 は s-r を使わない」に | 到着接続 |
| `test_turn_ledger.py::test_link_counts_flight_and_orders_together`(L09) | 最初 True、1件 record 後 False | 「接続で止まった」ことを保つため **cap(r)=4** に変える: 最初 True、1件 record 後も True、2件目の record 後に False(このとき `link_free(s-r, 1)` が False、`has_seats(r, 2)` は True、`projected("r", 2) == 3`)。名前を `test_link_counts_only_departures` に | 到着接続(接続の使用数は出発だけ)。cap(r)=3 のままだと2件目の後はゾーンも満員で、何で止まったか分からない |
| `test_turn_resolver.py::test_landing_still_uses_the_connection[1]`(T14) | 接続 `'s-r'` の違反 | 合法 `D1-r D2-s-r`。パラメタ [1]・[2] とも同じ期待にし、名前を `test_landing_frees_the_connection`、docstring を「着陸は接続を空けるので、容量1でも同じターンに出発できる」に | 到着接続。パラメタは「接続容量1で足りる」ことを示すために残す |
| `test_turn_resolver.py::test_reserved_restricted_zone_is_full`(T13) | 2ターン目の D2 の出発が `zone 'r'` の違反 | 2ターン目は合法 `D1-r D2-s-r`。3ターン目に指示なしで resolve すると `SimulationError`、メッセージは**完全一致**で `turn 3: D2 is stuck on connection 's-r': zone 'r' is full`。名前を `test_departure_then_stuck_on_connection` に | 予約表3(出発のターンには r に数えない)、Q-B(`TurnResolver` は予約を検査しない)、立ち退き6(新しい検出は「接続上で詰まった」だけ) |
| `test_turn_resolver.py::test_violation_leaves_state_unchanged[into_reserved_zone]`(T21d) | 違反で状態が変わらない | 違反にならないので場面を作り直す(下記)。ID を `stuck_on_connection` に | 同上 |
| `test_scheduler_maps.py::test_restricted_only_map_output`(R02) | 12行 | **8行**: `D1-hub-roof1` / `D1-roof1 D2-hub-roof1` / `D1-roof2 D2-roof1 D3-hub-roof1` / `D1-goal D2-roof2 D3-roof1 D4-hub-roof1` / `D2-goal D3-roof2 D4-roof1 D5-hub-roof1` / `D3-goal D4-roof2 D5-roof1` / `D4-goal D5-roof2` / `D5-goal`。docstring を「roof1 に着陸した機を次のターンに立ち退かせる予約で、毎ターン1機ずつ出発できる」に | 立ち退き(規則3・4。roof1 の在室機を roof2 へ立ち退かせる)。設計案 7.3 の期待と一致を確認済み |
| `tests/visualization/test_graphical_view.py::test_draws_every_turn_and_closes[restricted_only]`(VG06) | `len(turns) == 12` | `== 8`(`7 if subject else 8`) | R02 と同じマップ。`turns == plain_run(...)` の比較はそのまま |

### T21d の作り直し(違反の後に状態が変わらないこと)

`into_reserved_zone` を次の `stuck_on_connection` に置き換え、加えて通常のゾーン容量の違反 `zone_overflow`(T21e)を足す。

| ID | シナリオ | 期待 |
|---|---|---|
| T21d `stuck_on_connection` | `s-r r-g`、r は restricted(cap 1)、link(s-r)=2、2機。`resolve([O(1,"r")])` → `resolve([O(2,"r")])`(合法、`D1-r D2-s-r`)の後、指示 `[]` | `SimulationError`(「接続上で詰まった」)。`snapshot` が前後で等しい(**D2 の着陸も、ターン番号も進まない**) |
| T21e `zone_overflow` | `s-a a-g`、link(s-a)=2、2機。指示 `[O(1,"a"), O(2,"a")]` | `SimulationError`(`turn 1: zone 'a' would hold more than 1 drone(s)`)。`snapshot` が等しい |

- T21d は「着陸が先に適用されてから違反が見つかる」と状態が半端に変わる危険を検出する(着陸と指示の両方がある場面で、どちらも適用されない)。
- T22(違反の後も続けられる)は今の `landing_then_unknown_zone` のままでよい。詰まりからの続行は T30 で別に見る。

## B. 新しいケース

表記: `s-a a-g` は接続(記述順 = 宣言順)。`r` / `r1` / `z3` などのうち restricted は明記。hub の容量は省略時 1、接続容量は省略時 1。
`cap(a)=2`、`link(s-a)=2`。`O(1,"a")` は `MoveOrder(1, "a")`、`Rv(1,"a","b",3,3)` は `Reservation(drone_id=1, from_zone="a", zone="b", depart_turn=3, arrive_turn=3)`。
`at=` / `flying=` は `place` の引数。`place` の状態は `turn_number == 0` なので、着陸の予約は `depart_turn=0, arrive_turn=1`、
台帳・立ち退きの「このターン」は 1。

### ReservationTable(`tests/simulation/test_reservation_table.py`)

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定 |
|---|---|---|---|---|
| Q01 | reserve と数え方(ふつうの移動) | 空の表に `Rv(3,"a","g",2,2)`、`Rv(1,"b","g",2,2)` の順で reserve | `entering("g",2)==2`、`entering("g",3)==0`、`leaving("a",2)==1`、`leaving("b",2)==1`、`leaving("a",1)==0`、`due(2)` の drone_id が `[1, 3]`(**入れた順ではなく ID 順**)、`due(1)==[]`、`last_turn()==2` | 設計案 3.1 の API。規則5(予約した移動を ID 順で出す) |
| Q02 | restricted への移動 | `Rv(1,"s","r",2,3)` を reserve | `entering("r",2)==0`、`entering("r",3)==1`(入るのは arrive_turn)、`leaving("s",2)==1`、`leaving("s",3)==0`(出るのは depart_turn)、`due(2)` に1件、`due(3)==[]`、`last_turn()==3`(arrive_turn の最大) | 予約表(席は着陸のターンに数える)。depart / arrive の取り違えの検出 |
| Q03 | 1機が2行持つ | `y=Rv(1,"r","g",3,3)`、`x=Rv(1,"s","r",1,2)` の順で reserve。続けて `remove(1)` | `planned(1)==[x, y]`(depart_turn 順)。`remove(1)` は2件とも返し(順不同で比べる)、その後 `planned(1)==[]`、`entering("r",2)==0`、`leaving("r",3)==0`、`due(3)==[]`、`last_turn()==0`。もう一度 `remove(1)` と、行のない `remove(9)` は `[]` | 細部3(着陸+立ち退きの2行、`remove` は全部外す)。索引(4つの辞書)がすべて消えること |
| Q04 | rollback が reserve を戻す(入れ子) | `m1=mark()` → reserve `x` → `m2=mark()` → reserve `y` と `Rv(2,"a","b",4,4)` → `rollback(m2)` → `rollback(m1)` → もう一度 `rollback(m1)` | `rollback(m2)` の後: `planned(1)==[x]`、`planned(2)==[]`。`rollback(m1)` の後: すべて空、`last_turn()==0`、`mark()==m1`。2回目の `rollback(m1)` は何もしない(例外なし) | 立ち退き3-5(失敗したら仮の予約をすべて取り消す)、細部7。入れ子の試み(再帰)を部分的に戻せること |
| Q05 | rollback が remove を戻す | reserve `x` → `m=mark()` → `remove(1)` → `rollback(m)` | `planned(1)==[x]`、`entering("r",2)==1` | 規則7(仮に外した予約を、動けなかったら戻す。`Scheduler._decide` の `rollback(mark)`) |
| Q06 | clear | reserve `x`、`y` → `clear()` → `rollback(0)` | すべて空、`last_turn()==0`、`mark()==0`。`rollback(0)` で何も戻らない(取り消しの記録も消える) | 細部6(前のターンを渡されたら表を空にして始め直す) |
| Q07 | start_turn が着陸を読み込む | `s-r r-g`、r restricted、2機、`flying={1:("s","r")}`。`t.start_turn(state)` | `planned(1)==[Rv(1,"s","r",0,1)]`、`entering("r",1)==1`、`mark()==0`(着陸は取り消しの記録に載らない) | Q-A(着陸は毎ターン状態から作り直す)。`landings` の depart/arrive の値 |
| Q08 | start_turn を2回呼んでも着陸は1行 | Q07 の後にもう一度 `start_turn(state)` | `entering("r",1)==1`、`len(planned(1))==1` | 済んだ予約(depart_turn < 次のターン)を捨ててから入れ直すこと。二重に数えると席が減る |
| Q09 | start_turn が済んだ予約・古い予約を捨てる | `s-a a-b b-g`、cap(a)=cap(b)=2、3機、`at={1:"a",2:"a",3:"b"}`、`state.turn_number=2`。`keep=Rv(1,"a","b",4,4)`、`old=Rv(2,"a","b",2,2)`、`stale=Rv(3,"a","b",5,5)`(D3 は a にいない)を reserve → `start_turn(state)`。続けて `state.enter_zone(1,"g")`(配達)→ `start_turn(state)`。別に、`s-a a-g`・1機 `at={1:"a"}`(turn 0)で `d=Rv(1,"a","g",1,1)` を reserve → `start_turn` | 1回目: `planned(1)==[keep]`、`planned(2)==[]`(済んだ)、`planned(3)==[]`(出発元にいない)、`mark()==0`。配達の後: `planned(1)==[]`。別の表: `due(1)==[d]`(このターンに出る予約は残る) | 細部4(外から状態を変えられたときの防御)。境界(depart_turn == 次のターンは残す)。`start_turn` の後に `rollback(0)` しても何も変わらない(記録が消える)ことも同じケースで確かめる |
| Q10 | 飛行中の機の立ち退きは残る | `s-r r-g`、r restricted、2機、`flying={1:("s","r")}`。`start_turn` → `reserve(Rv(1,"r","g",2,2))` → もう一度 `start_turn` | `planned(1)` の (from_zone, depart_turn) が `[("s",0), ("r",2)]`(着陸と立ち退きの2行) | 細部3・4(飛行中の機は `transit_target == from_zone` なら有効)。S07 のターン2→3 の間の表の形 |

### Evictor(`tests/simulation/test_evictor.py`)

すべて `table, ledger, evictor = evictor_for(state)` で作り、`evictor.make_room(zone, first_turn, extra)` を呼ぶ。台帳のターンは 1。
「行」は `table.planned(id)` を全機ぶん集めたもの。

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定 |
|---|---|---|---|---|
| X01 | end への立ち退き(S07 のターン2) | `s-r r-g`、r restricted(cap 1)、2機、`flying={1:("s","r")}` | 前提: `ledger.has_seats(r, 2)` が False。`make_room(r, 2, 1)` が True、D1 の行が `[Rv(1,"s","r",0,1), Rv(1,"r","g",2,2)]` | 立ち退き3・4(end は常に席がある)。設計案 1 章の図 |
| X02 | 空いている normal への立ち退き | `s-r r-a a-g`、r restricted、2機、`at={1:"r"}` | `make_room(r, 2, 1)` が True、行は `[Rv(1,"r","a",2,2)]` だけ | 立ち退き4-1〜4-3(next_hops の一手、行き先の席 (W,T)) |
| X03 | 再帰(normal を通る) | X02 の網、3機、`at={1:"r", 3:"a"}`(a は cap 1 で満員) | True。行は `Rv(1,"r","a",2,2)` と `Rv(3,"a","g",2,2)` の2つ | 立ち退き4-4(W に席がなければ W の機を同じやり方で) |
| X04 | restricted への立ち退き(t+2 の席) | `s-r1 r1-r2 r2-g`、r1・r2 restricted。① 2機 `at={1:"r1"}` ② 3機 `at={1:"r1", 3:"r2"}` | ① True、行は `[Rv(1,"r1","r2",2,3)]`(席は (r2, 3) = t+2)。② True、行は `Rv(1,"r1","r2",2,3)` と `Rv(3,"r2","g",3,3)`(r2 の席をターン3に空ける) | 立ち退き4-3(W が restricted なら (W,T+1) 以降)。arrive の +1 の取り違えの検出 |
| X05 | 長い連鎖が終わる | `s-r1 r1-r2 r2-r3 r3-g`、r1〜r3 restricted、4機、`at={1:"r1",2:"r2",3:"r3"}` | True。行は `Rv(1,"r1","r2",2,3)`、`Rv(2,"r2","r3",3,4)`、`Rv(3,"r3","g",4,4)` の3つ。各行で `distance(zone) < distance(from_zone)`(5→3、3→1、1→0) | 設計案 2.1(距離が真に減るので再帰は終わる)、2.3(深さの制限がない)。無限再帰なら RecursionError で落ちる |
| X06 | 失敗したら全部取り消す(内側の接続・席も) | `s-z z-w w-g`、cap(z)=2、cap(w)=1、4機、`at={1:"z",2:"z",3:"w"}`。`m=table.mark()` → `make_room(z, 2, 2)` | **False**。`table.mark()==m`、全機の行が空、`ledger.link_free(w-g, 2)` と `link_free(z-w, 2)` が True、`projected("z",2)==2`、`projected("w",2)==1`。比較のため同じ状態で `make_room(z, 2, 1)` は True で、行は `Rv(1,"z","w",2,2)` と `Rv(3,"w","g",2,2)` | 立ち退き3-5・細部7。1機目(D1→w、そのために D3→g)は成功し、2機目(D2)は z-w がターン2に D1 で埋まって失敗する。**内側で取った w-g の接続と w の席まで戻る**ことを確かめる |
| X07 | 立ち退かせる機がいない | パラメタライズ: ① 先に出る予約がある: `s-r r-g`、r restricted、2機 `at={1:"r"}`。`evictor_for` の前に表へ `Rv(1,"r","g",3,3)` を入れる(`start_turn` の後)→ `make_room(r, 2, 1)` ② 着いたばかり: `flying={1:("s","r")}` で `make_room(r, 1, 1)` | どちらも False。表は前と同じ(① は D1 の行が `[Rv(1,"r","g",3,3)]` のまま、② は着陸の行だけ) | 細部5(候補は T−1 の終わりに確実にいて、このターンより後に出る予約のない機)。同じ機を2回立ち退かせないこと |
| X08 | 席がすでにある / end | ① `s-a a-g`、cap(a)=2、2機 `at={1:"a"}` で `make_room(a, 2, 1)` と `make_room(a, 2, 0)` ② `s-g`、3機で `make_room(g, 2, 5)` | すべて True で、表に行が増えない | 余計な立ち退きをしない。end は無制限 |
| X09 | 最初の候補の接続が埋まったら次の候補 | `s-r r-a r-b a-g b-g`、r restricted(cap 2)、4機、`at={1:"r",2:"r"}`。前提: `next_hops(r)` が `[a, b]` | `make_room(r, 2, 2)` が True。行は `Rv(1,"r","a",2,2)` と `Rv(2,"r","b",2,2)`(D2 は r-a がターン2に D1 で埋まるので b へ) | 立ち退き4-1・4-2(接続のターン T の使用数、候補を先頭から) |

### TurnLedger の追加(`tests/simulation/test_turn_ledger.py`)

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定 |
|---|---|---|---|---|
| L13 | `link_free`: このターンの記録は将来のターンに数えない | `s-a a-g`、cap(a)=2、2機。`record("s", hop(s,a))` | `link_free(s-a, 1)` が False、`link_free(s-a, 2)` が True | 細部1(このターンの指示は台帳だけが数える) |
| L14 | `link_free`: 予約した移動は出発のターンだけ、両方向で数える | ① `s-a a-g`、2機 `at={1:"a"}`、表に `Rv(1,"a","g",3,3)` ② `s-a a-b b-g`、2機 `at={1:"b",2:"a"}`、表に `Rv(1,"b","a",2,2)` ③ `s-r r-g`、r restricted、`flying={1:("s","r")}`(表は着陸だけ) | ① `link_free(a-g, 2)` True、`(a-g, 3)` False、`(a-g, 4)` True ② `link_free(a-b, 2)` False(宣言 `a-b` に対して b→a の予約) ③ `link_free(s-r, 1)` True(着陸は depart_turn=0 なのでターン1に数えない) | 到着接続、立ち退き4-2。`due(turn)` と `involves` の判定 |
| L15 | `has_seat(zone, turn, extra)` | `s-a a-g`、cap(a)=2、3機 `at={1:"a"}` | `has_seat(a,1,1)` True、`has_seat(a,1,2)` False、start・end は `extra=100` でも True | 立ち退きの `make_room(..., extra)` が使う境界 |
| L16 | `projected` は累積 | `s-a a-g`、cap(a)=2、3機 `at={1:"a"}`、表に `Rv(1,"a","g",3,3)`。その後 `record("s", hop(s,a))` | 記録前: ターン1〜4 で `[1, 1, 0, 0]`。記録後: `[2, 2, 1, 1]`、`projected("s",1)==1` | 「残る機 + 入る予約 − 出る予約」(設計案の用語)。将来のターンにも記録が残ること |
| L17 | restricted への記録は着陸のターンに数える | `s-r r-g`、r restricted、cap(r)=2、link(s-r)=2、2機。`record("s", hop(s,r))` | `projected("r",1)==0`、`projected("r",2)==1`。もう1機ぶん `has_room(hop(s,r))` が True | 予約表3、細部1(出発の指示は t+1 の +1) |
| L18 | 将来の予約された席は使わない(規則6、台帳の側) | `s-a a-g b-a`、2機 `at={2:"b"}`、表に `Rv(2,"b","a",3,3)`(D2 がターン3に a へ入る予約) | `has_seat(a,1,1)` は True だが、`has_seats(a,1)` と `has_room(hop(s,a))` は False。`horizon()==3` | 規則6(台帳は立ち退きをしない)。規則6' はスケジューラの側(D23)で確かめる |
| L19 | `horizon` と `arrival_turn` | ① `s-a a-g`、1機: `horizon()==2`。`turn_number=4` にすると `ledger.turn==5`、`horizon()==6`。そこへ `Rv(1,"s","a",7,8)` を足した表なら `horizon()==8` ② `s-r s-a r-g a-g`、r restricted、`turn_number=3`: `arrival_turn(r)==5`、`arrival_turn(a)==4`、`arrival_turn(g)==4` ③ `s-g`、g restricted: `arrival_turn(g)==2` | 左のとおり | `horizon` の下限(turn+1)と表の last_turn。restricted な end も2ターン(細部「試作との違い」4) |
| L20 | `cancel` は `record` を打ち消す | ① `s-a a-g`、2機: record → cancel ② `s-r r-g`、r restricted、2機: record(`projected("r",2)==1`)→ cancel | ① `has_room(hop(s,a))` True、`projected("a",1)==0`、`link_free(s-a,1)` True ② `projected("r",2)==0`、`has_room` True | 細部2(規則6' で入ってから立ち退きに失敗したときの取り消し) |
| L21 | 表を渡さないと着陸だけの表を作る | `s-r r-g`、r restricted、2機 `flying={1:("s","r")}`、`TurnLedger(state)` | `ledger.table.planned(1)==[Rv(1,"s","r",0,1)]`、`planned(2)==[]`、`ledger.table.mark()==0` | 細部2(テストや単独での利用) |

既存の L01〜L07・L10〜L12 は変えない(L07 は `has_room` が立ち退きをしないので False のまま。設計案 7.3)。

### TurnResolver の追加(`tests/simulation/test_turn_resolver.py`)

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定 |
|---|---|---|---|---|
| T25 | 着陸は最終負荷に数え、出ていく機が同じターンに空ける | パラメタライズ: ① `s-r r-g`、r restricted(cap 1)、2機 `at={2:"r"}`、`flying={1:("s","r")}`、指示 `[O(2,"g")]` ② `s-r r-q q-g`、r・q restricted、同じ配置で指示 `[O(2,"q")]` | ① `D1-r D2-g` ② `D1-r D2-r-q`(restricted へ出発した機も出発のターンに空きを作る) | 設計案 3.4(着陸を最終負荷に)、VII.3(出ていく機は同じターンに空きを作る) |
| T26 | restricted への出発は出発のターンに数えない | `s-r r-g`、r restricted(cap 1)、2機 `at={1:"r"}`、指示 `[O(2,"r")]`。次のターンは指示 `[]` | 1ターン目: `D2-s-r`(合法)、`occupancy("r")==1`、`reserved("r")==1`。2ターン目: `SimulationError`、メッセージ完全一致 `turn 2: D2 is stuck on connection 's-r': zone 'r' is full`、`snapshot` が等しい | 予約表3、Q-B(予約は検査しない)。「破れば詰まりとして見つかる」(規則8) |
| T27 | 2機が詰まるときは小さい ID を名指す | `s-r r-g`、r restricted(cap 1)、link(s-r)=2、3機、`flying={3:("s","r"), 2:("s","r")}`(入れる順を逆に)、指示 `[]` | `SimulationError`、完全一致 `turn 1: D2 is stuck on connection 's-r': zone 'r' is full` | メッセージが決定的であること(`landing.setdefault` の「ID の小さい順」) |
| T28 | 容量2: 残る機 + 着陸1 は合法、+2 は詰まり | `s-r r-g`、r restricted、cap(r)=2、link(s-r)=2、3機。① `at={1:"r"}`、`flying={2:("s","r")}` ② `at={1:"r"}`、`flying={2:("s","r"),3:("s","r")}`。どちらも指示 `[]` | ① `D2-r` ② `SimulationError`、完全一致 `turn 1: D2 is stuck on connection 's-r': zone 'r' is full` | 上限ちょうどは合法、1つ超えると詰まり(境界) |
| T29 | 着陸のないゾーンの違反は従来のメッセージ | `s-a a-g`、link(s-a)=2、2機、指示 `[O(1,"a"),O(2,"a")]` | 完全一致 `turn 1: zone 'a' would hold more than 1 drone(s)`(`stuck` を含まない) | 「接続上で詰まった」と通常の容量違反を区別して報告すること |
| T30 | 詰まりの後も続けられる | T13 の3ターン目(詰まり)の後、同じ状態に `[O(1,"g")]` | `D1-g D2-r`、`turn_number==3` | T22 と同じ性質を詰まりの場面で(違反のターンで状態が半端に変わっていないことの別の確かめ方) |

### Scheduler の追加(`tests/simulation/test_scheduler.py`)

規則7の網: `z0-g s-z1 z1-z0`、z0・z1 restricted、cap(z0)=2、cap(z1)=1、link(z0-g)=2、link(s-z1)=2、4機(以下 **網M7**)。
規則6'の網: `z3-z1 z4-z3 z3-z2 s-z4 z2-z4 z2-z0 z1-g z0-z1`、z3・z4 restricted、ほかは normal(cap 1)、link(z3-z1)=2、
link(z3-z2)=2、link(s-z4)=2、6機(以下 **網M6'**。ランダムなマップの探索で見つけた、規則6' が効く最小の例。下記「規則6' の例」)。
「ターン k まで進める」は、同じ `Scheduler` と `TurnResolver` で `decide_moves` → `resolve` を k 回くり返すこと。

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定 |
|---|---|---|---|---|
| D18 | 予約した移動はふつうの判断より先 | 網M7 をターン4まで進め、ターン5の `decide_moves` | `[O(3,"z0"), O(1,"g")]`。D3(z1 から、距離3)の予約した移動が、距離1の D1 の判断より**前**に並ぶ | 規則5(予約した移動はターンの最初)。距離の近い順なら D1 が先になるので、並びで区別できる |
| D19 | 凍結しない(規則7) | D18 の続き(ターン5を resolve すると `D1-g D2-z0 D3-z1-z0 D4-z1`)、ターン6の `decide_moves` | ターン5で D1 は(ターン6に z0→g へ出る立ち退きの予約を持っていたが)先に g へ動いている。D18 の指示に `O(1,"g")` があること自体が規則7の観察(凍結するなら D1 はターン6まで待つ)。ターン6の指示は `[O(2,"g"), O(4,"z0")]` で D1 を含まず、resolve が例外なく通る | 規則7・細部(先に動いたら予約を消す) |
| D20 | restricted への出発で立ち退きを作る(S07 のターン2) | `s-r r-g`、r restricted(cap 1)、2機、`flying={1:("s","r")}`。`decide_moves` → resolve → もう一度 `decide_moves` → resolve | 1回目 `[O(2,"r")]`、出力 `D1-r D2-s-r`。2回目 `[O(1,"g")]`(予約どおり)、出力 `D1-g D2-r`。1回目の前後で `snapshot` が等しい | 規則3・4。D12(cap 2、立ち退き不要)と対にする |
| D21 | 立ち退きに失敗したら待つ(K1 のターン2) | `s-r r-g`、r restricted、cap(r)=2、link(s-r)=2、4機、`flying={1:("s","r"),2:("s","r")}` | `[O(3,"r")]`(D4 は待つ。D2 を立ち退かせたいが r-g のターン3は D1 の立ち退きで埋まる) | 立ち退き3-5(失敗したら取り消して待つ)。取り消しが不完全だと D3 の予約まで消えて詰まる |
| D22 | 立ち退きは最後の手段(Q-C) | `s-a a-g s-b b-g`、a・b restricted、cap(a)=2、cap(b)=3、link(s-a)=2、6機、`flying={1:("s","a"),2:("s","a"),3:("s","b")}`(例1のターン2の状態) | `[O(4,"b"), O(5,"a")]`。D4 は先頭の候補 a(立ち退きで使える)ではなく、そのまま空いている b を選ぶ。D5 は1回目でどれも使えず(a は満員、s-b は D4 が使用)、2回目で a の立ち退きを使う | Q-C、最後の手段の報告 2 章(「最後の手段にしない」なら D4 が a になる) |
| D23 | 規則6' | 網M6' をターン6まで進め、ターン7・8の `decide_moves` | ターン7: `[O(5,"z3"), O(2,"g"), O(3,"z1")]`(D3 は、ターン8に D4 が z3 から入る予約のある z1 へ入り、自分を z1→g へ立ち退かせる予約を作る)。ターン8: `[O(3,"g"), O(4,"z1"), O(6,"z2")]`(D3 と D4 の予約した移動が ID 順で先頭) | 規則6'。規則6 なら D3 はターン7に z1 へ入れず待つ |
| D24 | 同じターンに呼び直しても同じ | ① D20 の状態で `decide_moves` を2回 ② K1(D21 の網、4機、全機 s)と、`s-r1 r1-r2 r2-r3 r3-g`(r1〜r3 restricted、3機)を、毎ターン `decide_moves` を3回呼んでから最後の結果で resolve して完走させる | ① 2回とも `[O(2,"r")]`、その後のターンも D20 と同じ(立ち退きが二重にならない)② 毎ターン3回の結果が等しく、K1 は6ターン、3連続は9ターンで完走(R09・R12 と同じ行) | 細部6(同じターンの再呼び出しは、そのターンの予約を取り消して計画し直す) |
| D25 | 新しい実行は表を空にして始める | K1 を1つの `Scheduler` で完走させた後、同じ `Scheduler` で新しい `SimulationState(network, 4)` から完走させる | 2回とも R10 の6行と同じ | 細部6(前のターンを渡されたら clear)。前の実行の予約が残ると結果が変わる |

- **D26(通常のテスト。2026-10-19 にバグを修正済み、acc1f71)**: 同じ `Scheduler` に、同じターン番号の**別の状態**を渡すと、
  渡された状態から計画し直す(前の状態の着陸は残らない)。`s-r r-g`、r restricted(cap 1)。
  `decide_moves(place(n,2,flying={1:("s","r")}))` の後に `decide_moves(place(n,2))` が、新しい `Scheduler` と同じ `[O(1,"r")]` を返す。
  `xfail` にはしない(確認したい点 1 は (a) に決定)。

### SimulationEngine の追加(`tests/simulation/test_engine.py`)

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定 |
|---|---|---|---|---|
| G12 | 「接続上で詰まった」はエンジンからそのまま伝わる | `s-r r-g`、r restricted(cap 1)、link(s-r)=2、2機。`scripted_scheduler(network, [[O(1,"r")], [O(2,"r")]])`、`recorder` を渡して `run` | `SimulationError`(`match="stuck on connection 's-r'"`)。render は2回(ターン1・2)だけで、`engine.state.turn_number == 2` | 規則8(違反した出力は出さない)。エンジンの docstring の Raises に追加された項目 |

### E2E(`tests/simulation/test_scheduler_maps.py`)

マップは `make_network` で組み、`World(network, nb_drones)` を `run_engine` / `run_checked` に渡す(またはマップ文字列を `write_map` で書く。
どちらでもよいが、接続名が出力に出るので宣言順は下の記述どおりにする)。各ケースとも `run_checked` でも完走することを確かめる
(毎ターン合法・最短・誰かが動く)。

| ID | マップ | 期待結果(出力の行、完全一致) | 意義・守る決定 |
|---|---|---|---|
| R09 | S07: `s-r r-g`、r restricted(cap 1)、2機 | 4行: `D1-s-r` / `D1-r D2-s-r` / `D1-g D2-r` / `D2-g` | 設計の目的(設計案 1 章)。旧規則では5行 |
| R10 | パラメタライズ。K1: `s-r r-g`、r restricted、cap(r)=2、link(s-r)=2、4機 / K2: `s-r r-a a-g`、r restricted、cap(r)=2、cap(a)=1、link(s-r)=2、link(r-a)=2、4機 | K1 6行: `D1-s-r D2-s-r` / `D1-r D2-r D3-s-r` / `D1-g D3-r D4-s-r` / `D2-g D4-r` / `D3-g` / `D4-g`。K2 7行: `D1-s-r D2-s-r` / `D1-r D2-r D3-s-r` / `D1-a D3-r D4-s-r` / `D1-g D2-a D4-r` / `D2-g D3-a` / `D3-g D4-a` / `D4-g`。どちらも `SimulationError`(詰まり)なし | 設計案 5.3(第2版では詰まった出口の細い restricted)。立ち退きの失敗と取り消しを通しで |
| R11 | 最後の手段の例1: `s-a a-g s-b b-g`、a・b restricted、cap(a)=2、cap(b)=3、link(s-a)=2、6機 | 5行: `D1-s-a D2-s-a D3-s-b` / `D1-a D2-a D3-b D4-s-b D5-s-a` / `D1-g D3-g D4-b D5-a D6-s-b` / `D2-g D4-g D6-b` / `D5-g D6-g` | Q-C(「最後の手段にしない」なら6ターン)。最後の手段の報告 2 章の表の右の列 |
| R12 | パラメタライズ(restricted が続く): ① `s-r1 r1-r2 r2-g`、2機 ② `s-r1 r1-r2 r2-r3 r3-g`、3機 ③ `s-r1 r1-n n-r2 r2-g`(n は normal)、3機。r* は restricted、cap 1 | ① 6行: `D1-s-r1` / `D1-r1 D2-s-r1` / `D1-r1-r2 D2-r1` / `D1-r2 D2-r1-r2` / `D1-g D2-r2` / `D2-g` ② 9行: `D1-s-r1` / `D1-r1 D2-s-r1` / `D1-r1-r2 D2-r1 D3-s-r1` / `D1-r2 D2-r1-r2 D3-r1` / `D1-r2-r3 D2-r2 D3-r1-r2` / `D1-r3 D2-r2-r3 D3-r2` / `D1-g D2-r3 D3-r2-r3` / `D2-g D3-r3` / `D3-g` ③ 8行: `D1-s-r1` / `D1-r1 D2-s-r1` / `D1-n D2-r1 D3-s-r1` / `D1-n-r2 D2-n D3-r1` / `D1-r2 D2-n-r2 D3-n` / `D1-g D2-r2 D3-n-r2` / `D2-g D3-r2` / `D3-g` | 設計案 2.3・5.1(restricted を通る立ち退きの再帰。② は毎ターン1機ずつ出発できる下限の9) |
| R13 | 網M6'(D23) | 11行: `D1-s-z4` / `D1-z4 D2-s-z4` / `D1-z4-z3 D2-z4 D3-s-z4` / `D1-z3 D2-z4-z3 D3-z4 D4-s-z4` / `D1-z1 D2-z3 D3-z2 D4-z4 D5-s-z4` / `D1-g D2-z1 D3-z0 D4-z4-z3 D5-z4 D6-s-z4` / `D2-g D3-z1 D4-z3 D5-z4-z3 D6-z4` / `D3-g D4-z1 D5-z3 D6-z2` / `D4-g D5-z1 D6-z0` / `D5-g D6-z1` / `D6-g` | 規則6'(規則6 では12行。ターン7で D3 が z1 に入れず、ターン9まで待つ) |
| R14 | 網M7(D18・D19) | 8行: `D1-s-z1` / `D1-z1 D2-s-z1` / `D1-z1-z0 D2-z1 D3-s-z1` / `D1-z0 D2-z1-z0 D3-z1 D4-s-z1` / `D1-g D2-z0 D3-z1-z0 D4-z1` / `D2-g D3-z0 D4-z1-z0` / `D3-g D4-z0` / `D4-g` | 規則5・7 を通しで |
| R15 | 性質テスト: restricted の多いランダムなマップ | 下記「R15 の生成方法」で 300 枚 | すべて `run_checked` で完走(`SimulationError` なし = 詰まり・容量違反なし、毎ターン合法・最短・誰かが動く、既定の上限内、全機配達) | 設計案 2.2(規則を守っていれば詰まらない)。手で作った例では届かない組み合わせの回帰検出 |

- **R04・R05 の閾値は変えない**(VII.7 の目標値 / IX の「45未満」。Stage 5 のテスト設計の申し送り3: 実測値で `==` にするとアルゴリズムの
  改善でも落ちる)。新しい実測値は記録として残す: circular_loop **10**(目標 15、旧 15)、the_impossible_dream **44**(< 45 で R05 は通る。
  `PROVIDED_MAPS` の challenger の行の `44` は使われていない参考値で、実測と一致)。ほかの配布マップ・課題の例は変わらない(4/4/4、8/8、13/16/26、7)。
- R03(毎ターンの不変条件)・R07(決定的)・R08(下限)は変更なしで通る(確認済み)。

#### R15 の生成方法

`random.Random(2026)` を1つ作り、300 回くり返す(マップごとに新しい seed を作らない。列が1本なので再現しやすい)。

1. hub の数 `n = randint(2, 8)`、名前は `z0`〜`z{n-1}`。
2. 到達できることを保証する鎖: `s`、`sample(hubs, n)`(並べ替え)、`g` を順につなぐ。
3. 追加の接続を `randint(0, n)` 本: `s` / hub / `g` から異なる2つを選び、どちら向きでもまだない組だけ足す(自己ループなし)。
4. 接続の並びを `shuffle`(宣言順 = `next_hops` の同点の並びが変わる)。
5. 各 hub を確率 0.6 で restricted、それ以外は normal。`max_drones = randint(1, 3)`、各接続の `max_link_capacity = randint(1, 2)`。
6. 機数 `randint(2, 10)`。
7. `make_network` で組み、`run_checked(World(network, k))`。

- 設計時の計測(上の手順の試作。乱数の呼び出し順が変わると数字も変わるので、作成フェーズで再計測して記録する):
  300 枚すべて完走、**立ち退きの予約が作られたマップ 149 枚**、立ち退きの試みの失敗(=取り消し)709 回、実行時間 約 0.2 秒
  (500 枚で 0.34 秒)。規則6' の立ち退きはこの 300 枚では0回(規則6' は R13・D23 で見る)。
- N=300 の理由: 立ち退き・取り消しの経路を数百回通るのに十分で、テスト全体(今 約2秒)への追加は 0.5 秒未満に収まる。
  設計案の試作では 7,832 枚・9,438 枚で詰まり0件だったので、これ以上増やしても新しく見つかる見込みは小さい。
- 失敗したときに再現できるよう、アサーションのメッセージにマップの記述(接続・種類・容量・機数)を入れる。
- priority は混ぜない(この変更と関係がなく、判断の順序のテストは D 系にある)。

### 規則6' の例(網M6')の見つけ方

設計案 8.1 の 20→19 の例(12機)はマップの記述が残っていないため、試作と同じ考え方で小さなランダムなマップ(hub 2〜6、2〜6機)を
探索し、規則6' の立ち退きが実際に作られ、かつ規則6(その立ち退きを禁止)より速くなる最小の例を選んだ(接続8本・6機、11 対 12)。
ターン7に、z0 にいる D3 が normal の z1(cap 1)へ入ろうとする。z1 にはターン8に、z3 から立ち退く D4 の席が予約されている
(ターン6に D5 のために作られた立ち退き)。規則6' では D3 が入り、同時に「D3 がターン8に z1→g へ出る」予約を作る。

## ケース数

| 系 | 新規 | 既存の更新 |
|---|---|---|
| Q(予約表) | 10 | — |
| X(立ち退き) | 9 | — |
| L(台帳) | 9(L13〜L21) | 2(L08・L09) |
| T(検査) | 6(T25〜T30)+ T21e | 3(T13・T14・T21d) |
| D(スケジューラ) | 8(D18〜D25) | 1(D12) |
| G(エンジン) | 1(G12) | — |
| R(E2E) | 7(R09〜R15) | 1(R02) |
| VG | — | 1(VG06) |
| **計** | **51**(T21e を含む。パラメタライズの展開後は X04・X07・X08 が各2、L14 が3、L19 が3、T25・T28 が各2、R10 が2、R12 が3) | **8** |

## 作成フェーズへの申し送り

1. Q 系は `ReservationTable` だけで完結する(状態が要るのは Q07〜Q10 だけ)。`Reservation` は frozen dataclass なので `==` で比べてよい。
   `remove` の戻り値の順序は契約にないので、順不同で比べる(`sorted(..., key=depart_turn)` か集合)。
2. X 系の `evictor_for` は、`start_turn` の後に予約を足したい場合(X07①)のために `table` を受け取る。足した後で `evictor_for(state, table)`
   を呼ぶと `start_turn` が2回走るが、`Rv(1,"r","g",3,3)` は D1 が r にいるので残る(Q09 の規則)。
3. D18・D19・D23・D24・R13・R14 は「ターン k まで進める」ので、ヘルパー `play(scheduler, resolver, state, turns)` を
   `test_scheduler.py` の中に置く(テストファイル同士の import はしない)。
4. 出力の行の比較は `fmt`(`TurnLogFormatter().format_turn`)で文字列にして、リストごと完全一致で比べる。
5. R15 は `test_scheduler_maps.py` に置き、既存の `run_checked` を使う(`World(network, k)` を直接作る)。
6. `tests/README.md` のカバレッジ欄に Q / X 系と各ファイルの追加分を書き、L08・L09・T13・T14・D12・R02・VG06 の説明
   (「到着のターンも接続容量に数える」「予約で満杯」「12行」など)を新しい規則に合わせて直す。
7. 更新する8件は、同じコミットで docstring も直す(今の docstring は旧規則を説明している)。

## バグ(`docs/bugs.md` に追記した)

- **同じターン番号の別の状態を渡すと、前の状態の着陸が予約表に残る**(`droneflow/simulation/scheduler.py:133-143` `_start_turn`)。
  同じターンの再呼び出しでは `rollback(self._turn_mark)` だけを行い `start_turn(state)` をやり直さないため、渡された状態が前と違うと、
  前の状態の着陸(と、それに合わせた判断)が残る。例: 上記 D26(新しい `Scheduler` なら `[O(1,"r")]` のところ `[]`)。
  アプリ(`droneflow/app.py:96`)は実行ごとに新しい `Scheduler` を作り、エンジンは毎ターン1回だけ呼ぶので、今の使い方では起きない。
  docstring の「Called again for the same turn, it drops the moves it planned for that turn and plans it again」と食い違う。
  → 2026-10-19 に修正済み(acc1f71。同じターンでも `start_turn(state)` をやり直す)。D26 は通常のテスト。

## 設計中に気づいた点・確認したい点

1. **D26(上のバグ)の扱い**: (a) `_start_turn` で同じターンでも `start_turn(state)` をやり直す(着陸は状態から作り直す方針、Q-A と一致)、
   (b) docstring に「同じ状態で」と前提を書くだけにする、のどちらにするか。(a) なら D26 を通常のテストにし、(b) なら D26 は作らない。
   決まるまでは `xfail(strict=True)` で置く案。
   → **(a) に決定・修正済み(acc1f71)**。D26 は通常のテストにする。
2. **「このターンの判断の途中で立ち退かされた機は待つ」の分岐(`decide_moves` の `continue`)に届く場面が見つからない**。
   立ち退かされるのは、立ち退かせる機より真にゴールに近いゾーンにいる機(next_hops で距離が減る)なので、判断の順序(距離が近い順)で
   必ず先に判断済みになる。防御のための分岐とみなしてテストを作らない案。到達できる場面をご存じなら教えてほしい。
3. **`evictor_for` が `Scheduler._positions` の規則を複製する**: 非公開メソッドを呼ばないための複製。規則が変わったときに X 系が
   気づかずに古い規則で通る危険がある。代わりに X 系をやめて D 系(スケジューラ経由)だけで立ち退きを見る案もあるが、
   失敗と取り消しの細部(X06 の内側の接続・席)は D 系からは観察しにくいので、複製を推奨する。
4. **R04・R05 の閾値**: 変えない案(上記)でよいか。circular_loop は目標 15 に対して 10 になり余裕ができたが、目標値で検査する方針は維持する。
5. **R15 の N=300 と生成方法**: 上記のとおりでよいか。実行時間を気にするなら 200 枚(約 0.13 秒、立ち退きのあるマップは約 100 枚)でも足りる。
6. **T14 のパラメタ**: 新しい規則では [1]・[2] が同じ期待になる。「接続容量1でも足りる」を示すため残す案。1本にまとめてもよい。
