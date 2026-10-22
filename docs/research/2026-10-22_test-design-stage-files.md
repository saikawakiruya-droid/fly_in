# テスト設計: パーサーと移動ロジックの単体実行(JSON ファイル経由)

- 日付: 2026-10-22
- フェーズ: **テスト設計**(テストコードはここでは書かない。作成は `test/stage_files` で行う)
- 対象ブランチ: `feature/stage_files`
- 対象コード: `droneflow/interchange/json_file.py`(`JsonObject`・`write_json`)、`interchange/world_file.py`
  (`world_to_json`・`world_from_json`・`WorldFile`)、`interchange/run_file.py`(`move_to_json`・`drone_to_json`・`state_to_json`・
  `RunRecorder`)、`errors.py`(`WorldFileError`・`OutputFileError`)、`cli.py`(3つのオプション)、`app.py`(`run`・`_load_world`・
  `_save_world`・`_save_run`)
- 参照した設計: `docs/research/2026-10-22_workflow-stage-files.md`
- 参照した決定: `docs/decisions.md` 2026-10-22「パーサーと移動ロジックを、JSON ファイルを経由して単体で動かせるようにする」1〜6
- 参照したバグ記録: `docs/bugs.md` 2026-10-18「マップのパスがエラーメッセージで『書かれたとおり』に出ない」(パスは入力どおりに出す)

## 方針

- 新しいテストは `tests/interchange/`(`droneflow/interchange/` に対応)に置く。CLI・Application・`fly_in.main` のテストは既存のファイルに足す。
- ID の接頭辞: **JO**(JsonObject と write_json)、**WF**(World のファイル)、**RR**(実行の記録)、**SC**(CLI)、**SA**(Application)、
  **SM**(`fly_in.main`)。既存の ID とは重ならない。
- 既存のフィクスチャを使う: `write_map`・`load_world`・`subject_map`・`scheduler_output`・`make_network`・`place`・`snapshot`・
  `stuck_after`・`no_pygame`。ファイルは `tmp_path` の下だけに書く。
- 書けないパスは「存在しないディレクトリの下」(`tmp_path / "no_dir" / "x.json"`)で作る。Linux・Windows の両方で `OSError`
  (ENOENT)になり、権限の操作が要らない。
- 不正な World は、課題の例を `world_to_json` した辞書を1か所だけ書き換えて作る(どのフィールドの検査かが1対1で分かる)。

## A. `JsonObject` と `write_json`(`tests/interchange/test_json_file.py`)

| ID | 何を確かめるか | 入力 | 期待 |
|---|---|---|---|
| JO01 | オブジェクトでないものは場所つきで拒否 | `JsonObject([])`、`JsonObject(3, "zones[1]")` | `ValueError("top level: must be an object")`、`"zones[1]: must be an object"` |
| JO02 | 欠けたキー | `JsonObject({}).value("x")`、`JsonObject({}, "a").value("x")` | `"x: missing"`、`"a.x: missing"` |
| JO03 | 整数: bool・小数・文字列は整数でない | `integer` に `True`・`1.0`・`"1"` | `"k: must be an integer"`。`5` はそのまま `5` |
| JO04 | 正の整数 | `positive` に `0`・`-1` / `1` | `"k: must be a positive integer"` / `1` |
| JO05 | null を許すもの | `optional_positive` / `optional_text` に `None` | `None`。値があれば `positive` / `text` と同じ検査(`optional_positive(0)` は拒否) |
| JO06 | 文字列 | `text` に `3` | `"k: must be a string"` |
| JO07 | 列挙値 | `member("t", ZoneType)` に `"priority"` / `"lava"` / `3` | `ZoneType.PRIORITY` / `"t: must be one of normal, blocked, restricted, priority, got 'lava'"` / `"t: must be a string"` |
| JO08 | オブジェクトのリスト | `objects("zones")` に `{}` / `[{}, 1]` | `"zones: must be a list"` / 2つ目で `"zones[1]: must be an object"`。1つ目の `where("name") == "zones[0].name"` |
| JO09 | 書き出しの形 | `write_json(str(p), {"a": [1], "名前": "é"})` | ファイルが UTF-8 で、`json.loads` で元に戻り、インデント2で、最後が改行。ASCII 以外はそのまま(`\u` に変えない) |
| JO10 | 書けないとき | `write_json(str(tmp_path / "no_dir" / "x.json"), {})` | `OutputFileError`。`path` は渡したとおりの文字列、`reason == "No such file or directory"`、メッセージ `cannot write '<path>': No such file or directory`。`OSError` が `__cause__` |
| JO11 | 書けないときの表示名(作成のフェーズで追加) | `write_json(tmp_path / "no_dir" / "x.json", {}, name="./no_dir/x.json")` | `OutputFileError.path == "./no_dir/x.json"`(開いたパスではなく入力どおり) |

## B. World のファイル(`tests/interchange/test_world_file.py`)

| ID | 何を確かめるか | 入力 | 期待 |
|---|---|---|---|
| WF01 | 往復で同じ World | 課題の例を `load_world` | `world_from_json(world_to_json(w))` の `zones`(宣言順の `Zone` のリスト)・`connections`・`nb_drones` が元と等しい(`Zone`・`Connection` は frozen の dataclass で `==` が使える) |
| WF02 | JSON の形 | 同上の `world_to_json` | キーが `format, version, nb_drones, zones, connections` の順、`format == "fly_in.world"`、`version == 1`。`zones[0] == {"name": "hub", "x": 0, "y": 0, "zone_type": "normal", "role": "start_hub", "color": "green", "max_drones": None}`、corridorA は `"priority"`・`max_drones: 2`、`connections[4] == {"zone_a": "corridorA", "zone_b": "tunnelB", "max_link_capacity": 2}` |
| WF03 | 一度 JSON の文字列にしても同じ | `json.loads(json.dumps(world_to_json(w)))` を `world_from_json` | WF01 と同じ |
| WF04 | 不正な World(パラメータ化。1か所だけ書き換え) | 下の表 | `ValueError`、メッセージが表のとおり |
| WF05 | start/end の `max_drones` はマップと同じく無視 | `zones[0].max_drones = 3` | 読めて、`max_drones is None` |
| WF06 | `WorldFile` の往復 | `WorldFile(p).write(w)` → `WorldFile(p).read()` | WF01 と同じ。ファイルは `write_json` の形(インデント2) |
| WF07 | JSON でないファイル | 中身 `"nb_drones: 5\n"` | `WorldFileError`。`path` は渡したとおり、メッセージ `invalid world file '<path>': not JSON: Expecting value (line 1)` |
| WF08 | 不正な World のファイル | WF04 の1つ(`nb_drones: 0`)をファイルに | `WorldFileError`、`reason == "nb_drones: must be a positive integer"` |
| WF09 | 開けない・UTF-8 でない | 存在しないパス / バイト列 `b"\xff"` | `FileNotFoundError`(`OSError`)/ `UnicodeDecodeError`。どちらも `WorldFileError` にしない(`Application` が `MapFileError` にする) |

WF04 の表(課題の例の `world_to_json` を書き換える。zones の添字は宣言順: 0 hub, 1 goal, 2 roof1, 3 roof2, 4 corridorA, 5 tunnelB, 6 obstacleX。
connections: 0 hub-roof1, 1 hub-corridorA, 2 roof1-roof2, 3 roof2-goal, 4 corridorA-tunnelB, 5 tunnelB-goal):

| # | 書き換え | メッセージ |
|---|---|---|
| a | 全体を `[]` | `top level: must be an object` |
| b | `format = "fly_in.run"` | `format: must be 'fly_in.world'` |
| c | `version = 2` | `version: must be 1` |
| d | `nb_drones = 0` | `nb_drones: must be a positive integer` |
| e | `zones` を削除 | `zones: missing` |
| f | `zones[2].x = "3"` | `zones[2].x: must be an integer` |
| g | `zones[2].name = "roof-1"` | `zones[2].name: must not contain '-', got 'roof-1'` |
| h | `zones[3].name = "roof1"` | `zones[3].name: duplicate zone name: roof1` |
| i | `zones[2].role = "start_hub"` | `zones[2].name: duplicate start_hub` |
| j | `zones[2].zone_type = "lava"` | `zones[2].zone_type: must be one of normal, blocked, restricted, priority, got 'lava'` |
| k | `zones[2].max_drones = 0` | `zones[2].max_drones: must be a positive integer` |
| l | `zones[2].max_drones = None`(hub) | `zones[2].max_drones: must be an integer` |
| m | `zones[0].zone_type = "blocked"` | `zones[0].zone_type: start_hub cannot be blocked` |
| n | `zones[1].zone_type = "blocked"` | `zones[1].zone_type: end_hub cannot be blocked` |
| o | `zones[2].color = 1` | `zones[2].color: must be a string` |
| p | `connections[0].zone_b = "nowhere"` | `connections[0].zone_a: unknown zone: nowhere` |
| q | `connections` の末尾に `{"zone_a": "roof1", "zone_b": "hub", "max_link_capacity": 1}` | `connections[6].zone_a: duplicate connection: roof1-hub` |
| r | `connections[4].max_link_capacity = 0` | `connections[4].max_link_capacity: must be a positive integer` |
| s | `zones` から goal を削除し、goal を使う接続(3, 5)も削除 | `zones: missing end_hub` |

## C. 実行の記録(`tests/interchange/test_run_file.py`)

| ID | 何を確かめるか | 入力 | 期待 |
|---|---|---|---|
| RR01 | 移動の形 | `Move(1, "a", "s-a")`、`Move(2, "r")`(着陸) | `{"drone_id": 1, "destination": "a", "connection": "s-a"}`、`connection` が `None` |
| RR02 | 状態の形(飛行中を含む) | `make_network("s-a a-g s-r r-g", types={"r": RESTRICTED}, capacity={"a": 2})`、`place(n, 4, at={1: "a", 2: "g"}, flying={3: ("s", "r")})` | `delivered_count == 1`。`drones` は D1・D3・D4 の順で、D2(配達済み)はない。D3 は `{"status": "in_transit", "zone": None, "connection": "s-r", "target": "r"}`。`zones == {"s": {"occupancy": 1, "reserved": 0}, "a": {...1, 0}, "r": {"occupancy": 0, "reserved": 1}}`(空の g はない、宣言順)。`connections == {"s-r": 1}` |
| RR03 | 初期状態 | `place(n, 2)` | `zones == {"s": {"occupancy": 2, "reserved": 0}}`、`connections == {}`、2機とも `at_zone` で `zone == "s"` |
| RR04 | 課題の例を通しで記録 | `SimulationEngine(world, Scheduler(...)).run(recorder)`(課題の例) | `to_json()` の `format == "fly_in.run"`・`version == 1`・`nb_drones == 5`・`complete is True`。`turns` は6件で `turn` が 0〜5。ターン0は `log == ""`・`moves == []`・5機が hub。ターン1〜5の `log` が `scheduler_output`。最後のターンは `drones == []`・`delivered_count == 5`・`zones == {}` |
| RR05 | 飛行中の記録(課題の例のターン2。README の抜粋と同じ) | RR04 の `turns[2]` | D4 が `in_transit`・`connection == "hub-roof1"`・`target == "roof1"`、`zones["roof1"] == {"occupancy": 1, "reserved": 1}`、`connections == {"hub-roof1": 1}`。D4 の移動は `{"drone_id": 4, "destination": "hub-roof1", "connection": "hub-roof1"}` |
| RR06 | 途中で止まった実行 | `StuckScheduler`(`stuck_after(2)` で作る)で `engine.run(recorder)` | `SimulationError`。`complete is False`、`turns` は3件(0〜2) |
| RR07 | 状態を変えない(observer は読むだけ) | RR02 の状態で `begin` と `render(state, [])` | 前後で `snapshot(state)` が等しい |
| RR08 | `to_json` は控えの写し | `to_json()["turns"].append(...)` の後でもう一度 `to_json()` | 件数が変わらない |
| RR09 | `write` | RR04 の後で `recorder.write(str(p))` | `json.loads(p.read_text("utf-8")) == recorder.to_json()`。書けないパスは `OutputFileError`(JO10 と同じ) |
| RR10 | `close` は何も書かない | `begin` → `close` | `tmp_path` にファイルができない(例外も出ない) |

## D. CLI(`tests/test_cli.py` に追加)

| ID | 何を確かめるか | 入力 | 期待 |
|---|---|---|---|
| SC01 | 既定値 | `parse_args(["m.txt"])` | `parse_only is None`、`from_world is False`、`save_run is None`。`Args(Path("m.txt"))` と等しい |
| SC02 | 入力どおりの文字列で持つ | `["m.txt", "--parse-only", "./out/w.json"]`、`["w.json", "--from-world", "--save-run", "./r.json"]` | `parse_only == "./out/w.json"`(`Path` にしない)。`from_world is True`・`save_run == "./r.json"` |
| SC03 | `--parse-only` と `--save-run` は排他 | 両方を指定 | `SystemExit` の code 2、stderr に `argument --save-run: not allowed with argument --parse-only` |
| SC04 | `--from-world` と `--parse-only` は一緒に使える | `["w.json", "--from-world", "--parse-only", "x.json"]` | エラーにならない |
| SC05 | ヘルプに追加機能の見出し | `build_parser().format_help()` | `stages on their own (additional features)` と3つのオプションを含む |

## E. Application(`tests/test_app.py` に追加)

| ID | 何を確かめるか | 入力 | 期待 |
|---|---|---|---|
| SA01 | `--parse-only` はパーサーだけ | 課題の例、`parse_only=str(tmp_path / "w.json")` | stdout が空。stderr が `world: wrote <path> (7 zones, 6 connections, 5 drones)\n` だけ(まとめがない)。ファイルの中身が `world_to_json(load_world(subject_map))` と等しい |
| SA02 | `--parse-only` は表示を作らない | SA01 に `visual="graphical"` と `no_pygame` | `VisualizationError` にならず、SA01 と同じ出力 |
| SA03 | `--from-world` はふつうの実行と同じ | SA01 のファイルを `Args(Path(p), visual="none", from_world=True)` | stdout が `log`(scheduler_output)、stderr が `SUMMARY + "\n"` |
| SA04 | `--from-world` の不正なファイル | WF08 のファイル | `WorldFileError`、stdout は空 |
| SA05 | `--from-world` の読めないファイル | 存在しないパス / `b"\xff"` のファイル。パスは `map_arg` に入力どおりの文字列を渡す | `MapFileError`。`cannot read map file '<入力どおり>': No such file or directory` / `...: not UTF-8 text` |
| SA06 | `--from-world` と `--parse-only` で書き直せる | SA01 のファイルを読み、別のパスに `--parse-only` | 2つのファイルの JSON が等しい |
| SA07 | `--save-run` | 課題の例、`visual="none"`、`save_run=str(p)` | stdout が `log`。stderr が `run: wrote <path>\n` + `SUMMARY + "\n"`(この順)。ファイルの `complete is True`、ターン1〜5の `log` を改行でつないだものが stdout と等しい |
| SA08 | 成功後に書けなければエラー | `save_run` が書けないパス | `OutputFileError`。stdout にはターンログ全部が出ている(書くのは実行の後)。stderr にまとめは出ない |
| SA09 | 途中で失敗しても、そこまでを書く | `stuck_after(2)`、`save_run=str(p)` | `SimulationError`(元のエラー)。ファイルの `complete is False`、`turns` は3件。stderr に `run: wrote <path>` |
| SA10 | 途中で失敗し、しかも書けない | `stuck_after(2)`、書けないパス | `SimulationError` のまま(`OutputFileError` にならない)。stderr に `warning: cannot write '<path>': No such file or directory` |
| SA11 | `--save-run` なしでは記録しない | ふつうの実行 | `tmp_path` に JSON ができない、stderr に `run:` がない(既存の AA 系の出力が変わらないことは既存テストで担保) |

## F. `fly_in.main`(`tests/test_fly_in.py` に追加)

| ID | 何を確かめるか | 入力 | 期待 |
|---|---|---|---|
| SM01 | 書けない `--parse-only` は終了コード 1 | `call_main(map, "--parse-only", <書けないパス>)` | 1、stderr が `error: cannot write '<path>': No such file or directory\n`、stdout が空 |
| SM02 | 不正な World のファイルは終了コード 1 | `call_main(<JSON でないファイル>, "--from-world")` | 1、stderr が `error: invalid world file '<path>': not JSON: Expecting value (line 1)\n` |
| SM03 | パーサー → ファイル → シミュレーションの通し | `call_main(map, "--parse-only", w)` → `call_main(w, "--from-world", "--visual", "none")` | どちらも 0。2回目の stdout が `log`。(Makefile の `run` と同じ入口で動く) |

## 作成のフェーズの結果(2026-10-22、`test/stage_files`)

- 設計どおりに作成した。pytest **818 passed**(前回 745 から +73)、`flake8 .`・`mypy . --strict`・`mypy . $(MYPY_FLAGS)` はエラーなし。
- SA05 が `--from-world` の不具合を見つけた: `Application` が入力どおりの表示名(`map_arg`)でファイルを開いていた
  (`docs/bugs.md` 2026-10-22)。`feature/stage_files` で直し(`WorldFile(path, name)`・`write_json(..., name)`)、テストのブランチにマージした。
  これに合わせて JO11 を足した。
- SA08 は `OutputFileError.path` ではなくメッセージで確かめる(`run_failing` が返すのは `BaseException` の情報のため)。
