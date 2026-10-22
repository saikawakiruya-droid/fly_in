# テスト設計: 名前と型の整理(2026-10-22)へのテストの追従

- 日付: 2026-10-22
- フェーズ: **テスト設計**(テストコードはまだ書かない。作成は別フェーズで行う)
- 対象ブランチ: `test/refactor_review`(1370692。`git diff 83b70ed..HEAD -- droneflow`)
- 対象コード: `simulation/reservation_table.py`(`Reservation.to_zone`、`entering/leaving(zone_name, ...)`)、`simulation/state.py`
  (`MoveOrder.zone_name`)、`simulation/turn_ledger.py`(`planning_turn`・`has_seat_from`・`fits`・`projected_load`・非公開の `_table`)、
  `parsing/map_format.py`(`FieldValues`・`Endpoints`・`metadata_keys` が frozenset)、`parsing/line_tokenizer.py`(`RawLine` が tuple / Mapping)、
  `cli.py`(`VisualMode`・`VISUAL_MODES = get_args(VisualMode)`)、`output/turn_log_view.py` → `output/turn_log_printer.py`
- 参照した設計: `docs/research/2026-10-21_workflow-refactor-review.md` の「追記(2026-10-22): 名前と型の一致を優先した追加の整理」
- 参照した決定: `docs/decisions.md` 2026-10-22 の3(命名と型の指摘を直す。挙動は変えない)
- 参照したバグ記録: `docs/bugs.md`(この整理で対象が変わる記録はない)
- 前回のテスト設計(表の列・ID の付け方を合わせる): `2026-10-21_test-design-refactor-review.md`

## 方針

- 今のテストは**収集の段階で3件のエラー**(`turn_log_view` の import)。import を直すと **71 failed / 662 passed**
  (古い属性名の `AttributeError`)、`mypy . --strict` は42件のエラー(古い名前と、`Args` に `str` を渡すところ)。
- 古い名前を新しい名前に置き換えるだけで、期待値は1つも変えない(挙動が変わっていないため)。例外は L21 だけで、非公開になった
  `TurnLedger._table` を見ずに、公開の `projected_load` / `horizon` で同じこと(表を渡さないと着陸だけの表を作る)を確かめる。
- テストは非公開の `_table` を使わない。表を見たいテストは、これまでどおり自分で作った表(`evictor_for` / `taker_for` /
  `ledger_with` が返す・受け取る表)を見る。
- 改名したモジュールに対応するテストファイルも改名する(`tests/output/test_turn_log_view.py` → `test_turn_log_printer.py`)。
- 新しいケースは接頭辞 **NT**(naming/typing)。既存の ID とは重ならない。
- 検証: リポジトリの外(スクラッチ)に `git archive HEAD` で複製し、A と B の変更をすべて当てて、`pytest` が **745 passed**
  (A だけで 733 passed。B が12件)、`flake8 .`・`mypy . --strict`・`mypy . $(MYPY_FLAGS)` がエラーなしまで確かめた(2026-10-22)。

## A. 失敗するテストと直し方

| 対象(ファイル・テスト) | 失敗の理由 | 直し方 |
|---|---|---|
| `tests/output/test_turn_log_view.py`(AP01〜AP04)・`tests/test_app.py`・`tests/test_fly_in.py` | 収集エラー: `droneflow.output.turn_log_view` がない | import を `droneflow.output.turn_log_printer` に。`test_turn_log_view.py` は `git mv` で `test_turn_log_printer.py` に改名し、モジュール docstring の名前も直す |
| `tests/parsing/test_line_tokenizer.py`: `test_splits_positional_tokens_and_metadata`・`test_header_is_tokenized_separately` | `positional` が tuple になり、リストとの比較が偽 | `== ("h", "2", "3")`・`== ("4",)` と比べる。`metadata == {...}` は Mapping と dict の比較で真のまま(変えない) |
| `tests/simulation/test_scheduler_maps.py`: `run_checked`(115〜129行。毎ターンの不変条件を見る全テスト)・`orders_by_turn`(591行) | `MoveOrder.zone` がない(39件ほか) | `order.zone` → `order.zone_name`(7か所) |
| `tests/simulation/test_scheduler.py`: `orders_by_turn`(522行。`test_detour_away_from_the_end_zone` ほか2件) | 同上 | `order.zone` → `order.zone_name` |
| `tests/simulation/test_turn_ledger.py`: `has_room` ヘルパー(L01〜L12 の12件が使う) | `ledger.turn`・`has_seats` がない | `turn = ledger.planning_turn` を置き、`link_free(hop.connection, turn) and ledger.has_seat_from(...)`(1行が79字を超えないように変数に出す) |
| 同: L15 `test_has_seat_with_extra` | `has_seat` がない | `ledger.fits(...)`。関数名も `test_fits_with_extra` に(docstring は変えない) |
| 同: L16・L17・L20(`projected`)、L18(`has_seat` / `has_seats`)、L19(`ledger.turn == 5`) | 古い名前 | `projected_load`・`fits`・`has_seat_from`・`planning_turn` |
| 同: L21 `test_ledger_without_table_loads_landings` | `ledger.table` が非公開に(mypy: attr-defined) | `moves_of(ledger.table, ...)` と `mark() == 0` をやめ、公開の値で確かめる: `[projected_load("r", t) for t in (1, 2, 3)] == [1, 1, 1]`(`state.occupancy("r")` は 0 なので、1 は着陸の予約から来る)、`projected_load("s", 1) == 1`、`horizon() == 2`(着陸のほかに予約がない)。引数の `moves_of` は不要になる |
| `tests/simulation/test_evictor.py`: X01(`has_seats`)、X05 `test_long_chain_ends`(`move.zone`)、X06(`projected`) | 古い名前 | `has_seat_from`・`move.to_zone`・`projected_load` |
| `tests/simulation/test_hop_taker.py`: HT01(`projected`)、HT05(`has_seats` / `has_seat` / `projected`)、HT06(`projected`) | 古い名前 | `projected_load`・`has_seat_from`・`fits` |
| `tests/test_app.py`: AA08 `test_missing_pygame`、`tests/test_app_graphical.py`: AG01 `test_stdout_is_the_same_log`・AG03 `test_window_cannot_open` | mypy: `Args` の `visual` に `str` を渡している(実行は通る) | 引数の注釈を `visual: VisualMode` にし、`from droneflow.cli import Args, VisualMode` |

変更の要らないもの: `ReservationTable.entering/leaving` はテストではすべて位置引数で呼んでいる(Q01〜Q10)。`MoveOrder(...)`・
`Reservation(...)`(`Rv`)もすべて位置引数。`tests/conftest.py`・`tests/simulation/conftest.py` は変更なし。

## B. 新しいケース

| ID | ファイル | 内容 | 期待値 | 検証 |
|---|---|---|---|---|
| NT01 | `tests/parsing/test_map_format.py` | `FieldValues({"x": 3, "zone": ZoneType.PRIORITY})` の `get("x", int)`・`get("zone", ZoneType)` | `3`、`ZoneType.PRIORITY`(`is`) | 実行 |
| NT02 | 同(parametrize 3件) | `get("x", int)` に `{"x": "3"}`・`{}`・`{"x": None}` | `TypeError`、文言は `field 'x' is str, not int` / `field 'x' is NoneType, not int`(後の2件) | 実行 |
| NT03 | 同 | `get_optional`: 値が None・キーがない・`str` の値・`int` の値を `str` で | `None`・`None`・`"h"`・`TypeError("field 'x' is int, not str")` | 実行 |
| NT04 | 同 | `FieldValues(raw)` の後に `raw` を書き換える | 値は変わらない(コピーを持つ) | 実行 |
| NT05 | 同 | `to_endpoints("roof1-goal")` | `Endpoints("roof1", "goal")`、`zone_a`・`zone_b` で読める | 実行 |
| NT06 | 同 | `ZoneBuilder(ZoneRole.HUB)` と `build_connection` に `FieldValues` を渡す(color は None) | `Zone("h", 1, 2, NORMAL, HUB, None, max_drones=3)`・`Connection("a", "b", 2)` | 実行 |
| NT07 | 同 | 仕様と builder の食い違い: `x` を `to_zone_name`(文字列)で変換する `LineSpec`(builder は `ZoneBuilder(ZoneRole.START)`)の `build`、`endpoints` にタプルを入れた `build_connection` | `TypeError`(`field 'x' is str, not int`・`field 'endpoints' is tuple...`)。`ValueError` / `ParseError` ではない | 実行 |
| NT08 | 同 | hub の `metadata_keys` | `frozenset({"zone", "color", "max_drones"})`、`isinstance(..., frozenset)` | 実行 |
| NT09 | `tests/parsing/test_line_tokenizer.py` | `connection: a-b [max_link_capacity=2]` の `RawLine` | `positional` は tuple で `("a-b",)`、`metadata` は `Mapping` で `{"max_link_capacity": "2"}` | 実行 |
| NT10 | `tests/test_cli.py` | `VISUAL_MODES` と `get_args(VisualMode)` | 等しい(順序も)、`("terminal", "graphical", "both", "none")` | 実行 |

`_Frame`(グラフィカル表示の最後のフレーム)は非公開で、既存の VG のテスト(再描画)が挙動を守るので、新しいケースは足さない。

## tests/README.md の更新

- 69行: `tests/output/test_turn_log_view.py` → `tests/output/test_turn_log_printer.py`
- 263行: `droneflow/output/turn_log_view.py` → `droneflow/output/turn_log_printer.py`
- 173行(`test_turn_ledger.py` の説明): `has_seat` の `extra` → `fits` の `extra`、`projected` → `projected_load`。
  L21 の「表を渡さないと着陸だけの表を作ること」に「(公開の `projected_load` / `horizon` で確かめる)」を足す
- 55〜60行(`test_map_format.py`): 「`FieldValues` の型つきの読み出し(型違い・値なしは欄の名前つきの `TypeError`、
  `get_optional` の None)、`Endpoints`、builder が `FieldValues` から読むこと・仕様と builder の食い違いは `TypeError`、
  `metadata_keys` が frozenset(NT01〜NT08)」を足す
- 61〜64行(`test_line_tokenizer.py`): 「`RawLine` が tuple と Mapping(NT09)」を足す
- 75行(`test_cli.py`): 「`VISUAL_MODES` が `VisualMode` の値と同じ順(NT10)」を足す
