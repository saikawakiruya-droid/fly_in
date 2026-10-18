# テスト設計: CLI / Application / エントリポイント(`fly_in.py`)

- 日付: 2026-10-18
- フェーズ: **テスト設計**(テストコードはまだ書かない。作成フェーズは別途)
- 対象ブランチ: `test/cli_app_makefile`(`feature/cli_app_makefile` から分岐)
- 対象コード: `droneflow/cli.py`(`Args` / `build_parser` / `parse_args` / `_delay`)、`droneflow/app.py`(`Application` /
  `_GuardedView`)、`droneflow/output/turn_log_view.py`(`TurnLogPrinter`)、`droneflow/output/summary.py`(`RunSummary`)、
  `droneflow/errors.py`(`MapFileError` / `VisualizationError`)、`fly_in.py`(`main` / `_run` / `_is_closed_pipe` / `_silence_stdout`)。
  `Makefile` / `requirements.txt` / `setup.cfg` は単体テストの対象外(下記「手動で確認すること」)。
- 参照した決定: `docs/decisions.md`(2026-10-18 の全エントリ)
  - 「CLI のフェーズで実装する可視化まわりの方針」(以下 **可視化方針**)
  - 「ステップ実行…both ではグラフィカル側だけが進行を握る」(以下 **ステップ**)
  - 「Stage 7 のテスト設計で挙がった点の扱い」(以下 **S7点**。特に 2: begin の失敗でも close)
  - 「CLI の形(`--visual` / `--delay` / `--step`、`--debug` はなくす)」(以下 **CLI形**)
  - 「ターンログはエンジンの観測者 `TurnLogPrinter` がターンごとに stdout へ書く」(以下 **ログ**)
  - 「実行の最後に、総ターン数と副次指標2つを stderr に1行出す」(以下 **まとめ**)
  - 「エラーの扱い(マップが読めない、pygame がない・窓が開けない、Ctrl+C、パイプが閉じた)」(以下 **エラー**。番号はその決定の 1〜7)
  - 「ビューの `close()` の失敗は、実行の結果を変えずに警告1行にする」(以下 **close警告**)
  - 「Makefile / requirements.txt / setup.cfg」「`make run` の既定マップは課題の例」(以下 **Makefile** / **既定マップ**)
  - 「予期しない例外は最後の砦で1行にする(`make debug` では pdb に渡す)」(以下 **最後の砦**)
  - 2026-10-17「ターミナル表示は stderr に出し、stdout はターンログだけにする」(以下 **stderr**)
- 参照した資料: `docs/research/2026-10-18_workflow-cli-app.md`(設計・完了条件・レビュー時の確認事項)
- 参照したバグ記録: `docs/bugs.md`(2026-10-18「Windows で stdout のパイプが閉じると…EINVAL」は AM06・AM07 で守る)。
  本設計で2件を追記した(下記「設計中に見つけた実装の問題」)。
- 書式の手本: `docs/research/2026-10-18_test-design-stage7-visualization.md`

## 方針

- **プロセス内で呼ぶのを基本にする**。`Application(args, out, err)` は出力先を注入できるので、`io.StringIO` を2つ渡して
  stdout / stderr を文字列で比べる。`fly_in.main()` は `monkeypatch.setattr(sys, "argv", [...])` で引数を与え、`capsys` で見る
  (`main` は `sys.stdout` / `sys.stderr` を `Application` の構築時に読むので、capsys の差し替えが効く)。
- **サブプロセスは2回だけ**(AE01・AE02)。`[sys.executable, "fly_in.py", ...]` をリポジトリ直下を `cwd` にして走らせ、
  本当の終了コード・トレースバックが出ないこと・`if __name__ == "__main__"` の配線を確かめる。`text=True` で読む
  (Windows では stdout の改行が `\r\n` になるため。バイト比較はプロセス内のケースで行う)。
- **「stdout がモードによらずバイト単位で同じ」**は、`StringIO` に書かせた `out.getvalue()` を、課題の例の期待値
  `"\n".join(subject_output) + "\n"` と**完全一致**で比べることで表す(全モードが同じ1つの文字列に一致 = 互いに同一)。
  terminal / none は `tests/test_app.py`、graphical / both は pygame が要るので `tests/test_app_graphical.py` に分ける。
- **グラフィカルはヘッドレス**(`SDL_VIDEODRIVER=dummy`)で、`--delay 0` にし、`hold_final=True` の最後の待ちは
  `graphical_view._Window.wait_for_quit` を `monkeypatch` でスパイ(すぐ戻る関数)に差し替えて避ける(Stage 7 の VG14 と同じ手)。
  イベントの投入には頼らないが、万一のハングに備えて Stage 7 と同じ番犬タイマー(QUIT)を仕掛ける。pygame が無ければ
  `pytest.importorskip("pygame")` でファイルごと skip。
- **ステップ実行は待たずに、組み立てたビューを調べる**(`Application(args)._make_views()` の戻り値の `_GuardedView.name` /
  `.view` の型と属性)。`TerminalVisualizer.step` は「`step` かつ入力が端末」なので、`sys.stdin` を `isatty()` が True の
  `StringIO` に差し替えてから構築する(pytest の下の本物の stdin は端末でない)。
- **pygame が無い状態は `sys.modules` で作る**: `monkeypatch.setitem(sys.modules, "pygame", None)` と
  `monkeypatch.delitem(sys.modules, "droneflow.visualization.graphical_view", raising=False)`。こうすると
  `import pygame` が `ModuleNotFoundError(name="pygame")` になる(設計時に確認)。teardown で `sys.modules` は元に戻る。
- **窓が開けない状態は `SDL_VIDEODRIVER=nosuch`**(存在しないドライバ)で作る。`pygame.display.init()` が
  `pygame.error: nosuch not available` を出し、`VisualizationError("cannot open the graphical window: nosuch not available")`
  になる(設計時に確認)。コードの変更は要らない。
- **エラーの差し込みは `monkeypatch` で行う**: `fly_in.Application` をスタブ(`run` が指定の例外を出す)に差し替える
  (main の例外表のケース)、`droneflow.app.Scheduler` を止まるスケジューラに差し替える(`SimulationError`)、
  `droneflow.app.TerminalVisualizer.close` / `TurnLogPrinter.render` などを失敗する関数に差し替える。
- **パイプが閉じたケースはプロセス内**で、`fly_in._silence_stdout` をスパイに差し替える(本物は `sys.stdout.fileno()` に
  `os.dup2` するので、capsys の下では使えず、テストのプロセスの stdout も壊す)。本物のパイプでの確認は手動(下記)。
- 環境変数 `FLYIN_DEBUG` は、`fly_in.main` を呼ぶ全ケースで `monkeypatch.delenv(raising=False)` か `setenv` で明示する
  (開発者の環境に左右されないように)。
- 期待値の文字列(エラー文・まとめの行)は、設計時に `feature/cli_app_makefile` の実装で出力して確認した(アドホック、コミットしない)。
- `revie_case/` と scratchpad のスクリプトには依存しない。`maps.tar.gz` も使わない(配布マップの検査は Stage 5 で済んでいる)。

## ファイル構成

```
tests/
├── conftest.py                    # 変更なし(write_map / load_world / subject_map / subject_output を使う)
├── test_cli.py                    # 新規: AC01〜AC08(argparse、pygame 不要)
├── test_app.py                    # 新規: AA01〜AA14(Application、pygame 不要)
├── test_app_graphical.py          # 新規: AG01〜AG04(graphical / both、pygame が無ければ skip)
├── test_fly_in.py                 # 新規: AM01〜AM10(main の例外表)+ AE01〜AE02(サブプロセス)
└── output/
    ├── test_turn_log_view.py      # 新規: AP01〜AP04(TurnLogPrinter)
    └── test_summary.py            # 新規: AS01〜AS03(RunSummary)
```

- `cli.py` / `app.py` は `droneflow/` 直下なので、テストも `tests/` 直下に置く(構成の対応づけの方針どおり)。
  `fly_in.py` はリポジトリ直下なので `tests/test_fly_in.py`。
- ID の接頭辞は `A`(Application のフェーズ)+ 対象の1文字: `AC` = cli、`AP` = TurnLogPrinter、`AS` = summary、
  `AA` = Application、`AG` = Application のグラフィカル、`AM` = main、`AE` = サブプロセスの E2E。既存の ID と重ならない。
- `__init__.py` は置かない(既存と同じ)。`tests/test_app_graphical.py` を分けるのは、pygame が無い環境でも `test_app.py` を
  skip させないため(Stage 7 の `test_graphical_view.py` と同じ考え方)。
- `import fly_in` は、`droneflow` と同じく「リポジトリ直下がカレントで `python -m pytest`」(`make test` の形)で通る。

## 共有フィクスチャ・ヘルパー

### 既存(`tests/conftest.py`、変更なし)

`write_map`(`tmp_path/map.txt` を書いて `Path` を返す)、`subject_map` / `subject_output` を使う。
`EXPECTED_LOG = "\n".join(subject_output) + "\n"` を各テストで作る(またはファイル内の小さなフィクスチャ `expected_log`)。

### `tests/test_app.py` 内

| 名前 | 中身 | 使うケース |
|---|---|---|
| `TtyStringIO` | `isatty()` が True の `io.StringIO`(2行。`tests/visualization/conftest.py` のものと同じ。**決定: `tests/conftest.py` に上げて共有する**(作成フェーズで移す)。確認したい点 2) | AA04, AG02 |
| `run_app(args) -> tuple[str, str]` | `out, err = StringIO(), StringIO()`、`Application(args, out, err).run()`、`(out.getvalue(), err.getvalue())` を返す。例外はそのまま伝える(呼び出し側で `pytest.raises`) | AA01〜AA14 |
| `sample_path` フィクスチャ | `write_map(subject_map)` | ほぼ全部 |
| `no_pygame` フィクスチャ | 上記「方針」の `sys.modules` の差し替え | AA09, AA10 |
| `StuckScheduler` | `__init__(network, pathfinder)` で本物の `Scheduler` を作り、`decide_moves` を `ok_turns` 回だけ委譲し、以後は `[]` を返す(エンジンが `SimulationError("turn N: no drone moved, ...")` を出す)。`monkeypatch.setattr("droneflow.app.Scheduler", ...)` で差し替える。`ok_turns` は `functools.partial` か小さなファクトリで渡す | AA12, AA13 |
| `fail_close(monkeypatch)` | `monkeypatch.setattr(TerminalVisualizer, "close", ...)` で `RuntimeError("boom")` を出す(差し替える前の `close` を呼んでから送出し、flush は済ませる) | AA11, AA12, AM10 |
| `RecordingView` | `begin` / `render` / `close` で、注入された `out` の行数(`out.getvalue().count("\n")`)を記録するビュー。`monkeypatch.setattr("droneflow.app.TerminalVisualizer", factory)` で差し替える(`factory(stream=..., step=...)` の形を受ける) | AA03, AA13 |

### `tests/test_app_graphical.py` 内(pygame が要るのでファイル内に閉じる)

| 名前 | 中身 |
|---|---|
| `pygame = pytest.importorskip("pygame")` | ファイル先頭。無ければ全体 skip |
| `headless` フィクスチャ | `SDL_VIDEODRIVER=dummy` / `SDL_AUDIODRIVER=dummy` を `monkeypatch.setenv`、`_Window.wait_for_quit` を呼び出し回数を数えるスパイに差し替え、番犬 `pygame.time.set_timer(pygame.QUIT, 5000, loops=1)`(`display.init()` の後)、teardown で番犬を止めて `pygame.display.quit()`。スパイの呼び出し回数を返す |

### `tests/test_fly_in.py` 内

| 名前 | 中身 | 使うケース |
|---|---|---|
| `call_main(monkeypatch, *argv) -> int` | `monkeypatch.setattr(sys, "argv", ["fly_in.py", *argv])` して `fly_in.main()` の戻り値を返す | AM 全部 |
| `RaisingApp(exc)` | `fly_in.Application` の代わり。`__init__(args)` を受け、`run()` で `exc` を送出する。`monkeypatch.setattr(fly_in, "Application", ...)` | AM03〜AM08 |
| `silenced` フィクスチャ | `fly_in._silence_stdout` を呼び出し回数を数えるスパイに差し替える(**パイプのケース以外でも必ず差し替える**: 誤って本物が呼ばれるとテストのプロセスの stdout が devnull になる) | AM05〜AM08 |
| `no_debug` フィクスチャ | `monkeypatch.delenv("FLYIN_DEBUG", raising=False)`(autouse にしてよい) | AM 全部 |
| `run_script(*argv)` | `subprocess.run([sys.executable, "fly_in.py", *argv], cwd=<リポジトリ直下>, capture_output=True, text=True, stdin=subprocess.DEVNULL, env=<FLYIN_DEBUG を除いた os.environ のコピー>, timeout=60)` | AE01, AE02 |

## ケース一覧

表記: `run_app(Args(p, visual="none"))` などは `Args` を直接作る(`parse_args` を通さない)。`p` は `sample_path`。
`LOG` は `"\n".join(subject_output) + "\n"`(課題の例の7行)。`SUMMARY` は
`"summary: 7 turns, 5 drones, 5.00 turns per drone on average, 2.14 moves per turn"`。

### 引数(`tests/test_cli.py`、pygame 不要)

`parse_args(argv)` を直接呼ぶ。エラーは `pytest.raises(SystemExit)` の `.value.code` と `capsys.readouterr().err` で見る。

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定/仕様 |
|---|---|---|---|---|
| AC01 | 既定値 | `parse_args(["m.txt"])` | `Args(map_path=Path("m.txt"), visual="terminal", delay=0.5, step=False)` と等しい。`map_path` は `Path` 型 | CLI形 1(既定 `terminal` / `0.5`)、可視化方針 2・3 |
| AC02 | `--visual` の4つの値 | パラメタライズ: `terminal` / `graphical` / `both` / `none` | `args.visual` がその値。`VISUAL_MODES` と同じ4つ(順序込み) | CLI形 1 |
| AC03 | `--visual` の誤った値 | `["m.txt", "--visual", "gui"]`、`["m.txt", "--visual", "Terminal"]`(大文字) | `SystemExit`、code 2。stderr に `usage: fly_in.py` と `invalid choice: 'gui'`。stdout は空 | CLI形 3(argparse の慣例、終了コード2)。大文字小文字を区別すること |
| AC04 | `--delay` の受理 | パラメタライズ: `"0"` → 0.0、`"0.25"` → 0.25、`"1e3"` → 1000.0、`"-0"` → 0.0(-0.0 も可)、`"--delay=2"` の書き方 | `args.delay` がその値(float) | CLI形 3(0 以上の有限な数)。0 ちょうどは受理(境界) |
| AC05 | `--delay` の拒否 | パラメタライズ: `-1`、`-0.001`、`nan`、`inf`、`-inf`、`abc`、`""` | すべて `SystemExit` code 2。stderr の最後の行が `fly_in.py: error: argument --delay: ` で始まり、数でないもの(`abc`・`""`)は `not a number: 'abc'`、それ以外は `must be a finite number of seconds >= 0: '-1'`(書かれたとおりの値を `repr` で) | CLI形 3、`_delay` の2つの文言。`-1` が「未知のオプション」ではなく値として読まれること(argparse の負の数の扱い) |
| AC06 | 必須引数・未知のオプション | パラメタライズ: `[]`(MAP なし)、`["m.txt", "--debug"]`(なくしたオプション)、`["m.txt", "extra.txt"]` | `SystemExit` code 2。それぞれ `the following arguments are required: MAP` / `unrecognized arguments: --debug` / `unrecognized arguments: extra.txt` | CLI形 2(`--debug` はない)・3 |
| AC07 | `--step` | `["m.txt", "--step"]` と `["m.txt", "--visual", "none", "--step", "--delay", "3"]` | `step is True`。関係のないモードでも `--step` / `--delay` はエラーにならない | CLI形 4(関係のないモードでは無視、エラーにしない) |
| AC08 | `--help` | `["--help"]` | `SystemExit` code 0。**stdout** に `usage: fly_in.py`、`--visual {terminal,graphical,both,none}`、`--delay SECONDS`、`--step`、`(default: terminal)`、`(default: 0.5)` | `parse_args` の docstring(help は 0)。ヘルプの既定値の表示が定数と食い違わないこと |

### TurnLogPrinter(`tests/output/test_turn_log_view.py`、pygame 不要)

テスト内のスタブ `FlushCountingIO(io.StringIO)`: `flush` の回数と、各 `flush` の時点の `getvalue()` を記録する。
`closed` は `StringIO` の属性で見る。

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定/仕様 |
|---|---|---|---|---|
| AP01 | begin は何も書かない・既定の出力先 | ① `TurnLogPrinter(s).begin(state)` ② capsys の下で `TurnLogPrinter()` を**テスト内で**構築し、`render(state, [Move(1, "a")])` | ① `s.getvalue() == ""` ② `capsys` の `out == "D1-a\n"`、`err == ""` | ログ 1(turn 0 は出さない)。既定は構築時の `sys.stdout` |
| AP02 | 1ターン1行・1行ごとに flush | `render` を3回: `[Move(1,"a")]`、`[Move(1,"b"), Move(2,"a")]`、`[Move(2,"a-b")]` | `getvalue() == "D1-a\nD1-b D2-a\nD2-a-b\n"`。flush が3回以上で、各 render の直後の flush の時点でその行まで書かれている(記録の各値が `"D1-a\n"`、`"D1-a\nD1-b D2-a\n"`、…) | ログ 1(1行ごとに flush、パイプ・リダイレクトでも順序が崩れない)。フォーマット(Stage 6)は呼び出し順のまま |
| AP03 | 空のターンは書かない | `render(state, [])` を最初・途中に挟む | 空行が出ない(出力は空でないターンの行だけ)。空のターンでは flush もしない(記録が増えない) | ログ 1(空のターンは書かない。エンジンは空のターンを render しないが、プリンタ単体でも守る) |
| AP04 | close・フォーマッタの委譲 | ① `close()` ② スタブのフォーマッタ(`format_turn` が `"X"` を返し、受け取った `moves` を記録)を渡して `render` | ① flush が1回増え、`s.closed is False`(閉じない)。何も書かない ② 出力が `"X\n"`、スタブが受け取った `moves` は渡したものと同一(`is`) | `close` の docstring(ストリームは自分のものではない)。フォーマットは `TurnLogFormatter` に委譲(合成) |

### RunSummary(`tests/output/test_summary.py`、pygame 不要)

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定/仕様 |
|---|---|---|---|---|
| AS01 | 課題の例の数値と文言 | `subject_output` を `Move` のリストに戻したもの(`"D1-corridorA"` → `Move(1, "corridorA")`。小さなヘルパーで)、`nb_drones=5` | `RunSummary(turns=7, drones=5, average_turns_per_drone=5.0, moves_per_turn=15/7)`。`describe()` が `SUMMARY` と完全一致(15/7 = 2.142… が `2.14`) | まとめ(文言・2つの指標の定義・小数2桁)。CLI のケース(AA01)と同じ文字列 |
| AS02 | 配達ターン = 最後に出たターン | restricted の移動を含む: `[[Move(1,"s-r")], [Move(1,"r"), Move(2,"a")], [Move(1,"g"), Move(2,"g")]]`、`nb_drones=2` | `turns=3`、`average_turns_per_drone == 3.0`(D1 も D2 も3ターン目)、`moves_per_turn == 5/3`、`describe()` に `3.00 turns per drone`、`1.67 moves per turn`(切り上げの丸め) | まとめ(「最後に動いたターン」。接続名の項目も1手として数える) |
| AS03 | 空の実行 | `from_turns([], 0)`、`from_turns([], 3)` | 前者は全項目0 で `describe() == "summary: 0 turns, 0 drones, 0.00 turns per drone on average, 0.00 moves per turn"`。後者も例外なし(`ZeroDivisionError` にならない)で `0 turns, 3 drones`、平均は `0.00` | `from_turns` のゼロ除算の防御(エンジンは呼ばないが、関数としての境界) |

### Application(`tests/test_app.py`、pygame 不要)

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定/仕様 |
|---|---|---|---|---|
| AA01 | none: stdout は課題の形式だけ | `run_app(Args(p, visual="none"))` | `out == LOG`(バイト単位で一致)。`err == SUMMARY + "\n"`(stderr はまとめの1行だけ) | ログ 3、まとめ(毎回・stderr)、stderr |
| AA02 | terminal: stdout は none と同じ | `run_app(Args(p))`(既定 terminal、`--step` なし)。`NO_COLOR` は関係しないよう `color` の自動判定は StringIO なので off | `out == LOG`(AA01 と同一)。`err` は `=== Turn 0 (start)` で始まり、最後の行が `SUMMARY`。`out` に `===`・`\x1b`・`summary` を含まない | ログ 3、stderr(ターミナル表示は stderr)、まとめ(最後の行) |
| AA03 | ターンごとに出る・プリンタが先 | `RecordingView` で `TerminalVisualizer` を差し替え、`run_app(Args(p))` | `begin` の時点で stdout は0行、`render` の時点の行数が `[1, 2, 3, 4, 5, 6, 7]`(各ターンの行がフレームより先に書かれている)、`close` の時点で7行 | ログ 2(プリンタを先頭に置く)、可視化方針 1(最後にまとめてではなくターンごと) |
| AA04 | ステップ実行の組み立て(terminal / both) | `monkeypatch.setattr(sys, "stdin", TtyStringIO())`。パラメタライズ: ① `Args(p, "terminal", step=True)` ② `Args(p, "terminal")` ③ `Args(p, "terminal", delay=3)`。`app = Application(args, out, err)`、`views = app._make_views()` | ① `[v.name for v in views] == ["terminal"]`、`views[0].view` が `TerminalVisualizer` で `step is True`、`stream is err` ② `step is False` ③ 例外なし(`--delay` は terminal では無視) | ステップ(terminal は Enter で進む)、CLI形 4・5。ビューの出力先が注入した `err` |
| AA05 | none はビューなし | `Args(p, "none", delay=3, step=True)` で `_make_views()` | `[]`。pygame を import しない(`"droneflow.visualization.graphical_view" not in sys.modules` の差分で見る。事前に `monkeypatch.delitem(..., raising=False)`) | CLI形 4(none では `--step` を使わない)、エラー 3(pygame は graphical / both のときだけ) |
| AA06 | マップが読めない → `MapFileError` | パラメタライズ: ① 存在しないパス `tmp_path / "missing.txt"` ② ディレクトリ `tmp_path` ③ UTF-8 でないファイル(`write_bytes(b"nb_drones: 1\n\xff\n")`) | すべて `pytest.raises(MapFileError)`。`str(exc)` が `cannot read map file '<str(path)>': ` で始まる。① の理由は `No such file or directory`、③ は `not UTF-8 text`、② は空でない(Windows は `Permission denied`、POSIX は `Is a directory` なので文言は固定しない)。`__cause__` が ①② は `OSError`、③ は `UnicodeDecodeError`。`exc.path` / `exc.reason` が文の部品と一致。out / err は空 | エラー 2(`OSError` / `UnicodeDecodeError` を `_load_world` で変換。パーサーは変えない)。`FlyInError` の子であること |
| AA07 | パース・到達不能のエラーはそのまま伝わる | パラメタライズ: ① 1行目がコメント(`"# c\nnb_drones: 1\n"`)② start と end をつながない(`"nb_drones: 1\nstart_hub: s 0 0\nend_hub: g 1 1\n"`) | ① `ParseError`、`str == "line 1: the first line must be 'nb_drones: <n>'"` ② `UnreachableGoalError`、`str == "goal 'g' is unreachable from 's'"`。どちらも `MapFileError` に包まれない。out / err は空(ビューもまとめも出ない) | エラー 1、5(マップを読む → 到達可能か、が実行より先) |
| AA08 | pygame がない → `VisualizationError` | `no_pygame`。パラメタライズ: `visual="graphical"` / `"both"` | `VisualizationError`、`str ==` `"the graphical view needs pygame (pygame-ce): run 'make install' or 'pip install pygame-ce', or use --visual terminal"`。`__cause__` が `ModuleNotFoundError`(`name == "pygame"`)。**out も err も空**(both でもターミナルのフレームは出ない。ビューの組み立ては実行より前) | エラー 3・5(ビューを組み立ててから実行) |
| AA09 | 確認の順番 | `no_pygame`、`visual="graphical"`。パラメタライズ: ① 存在しないマップ ② AA07 ① のマップ ③ AA07 ② のマップ | それぞれ `MapFileError` / `ParseError` / `UnreachableGoalError`(`VisualizationError` ではない) | エラー 5(マップの誤りを pygame の案内より先に知らせる) |
| AA10 | pygame 以外の import の失敗は包まない | `monkeypatch.setitem(sys.modules, "droneflow.visualization.palette", None)` と `graphical_view` の削除、`visual="graphical"` | `ModuleNotFoundError` がそのまま伝わる(`VisualizationError` にならない)。`exc.name == "droneflow.visualization.palette"` | `_graphical_view` の `exc.name` の判定(バグを「pygame を入れて」と誤案内しない)。main では「internal error」になる |
| AA11 | 成功後の close の失敗は警告だけ | `fail_close`、`run_app(Args(p))` | 例外なし。`out == LOG`。`err` の最後の2行が `warning: could not close the terminal view: boom` と `SUMMARY`(この順) | close警告 1・2(終了コード・ログ・まとめを変えない。警告はまとめの前) |
| AA12 | 失敗後の close の失敗は元のエラーを隠さない | `StuckScheduler(ok_turns=0)`、`fail_close`、`run_app(Args(p))` | `pytest.raises(SimulationError, match="turn 1: no drone moved")`(`RuntimeError` ではない)。`err` に `warning: could not close the terminal view: boom` があり、`summary:` はない。`out == ""` | close警告 2(エンジンの `finally` の例外が元のエラーを置き換えない) |
| AA13 | 途中の `SimulationError` でも、出たログとビューの後始末は残る | `StuckScheduler(ok_turns=2)`、`RecordingView` で差し替え、`run_app(Args(p))` | `SimulationError("turn 3: no drone moved, ...")`(状態のターン番号は判断の前に進んでいるため `ok_turns + 1`)。`out` が `LOG` の最初の2行(`"D1-corridorA\nD1-tunnelB D2-corridorA\n"`)。`RecordingView.close` が1回呼ばれた。`err` に `summary:` がない | まとめ(エラーでは出さない)、ワークフローの挙動図(エラーでもビューは閉じ、それまでのログは stdout に出ている) |
| AA14 | ターンログのプリンタは包まない | `monkeypatch.setattr(TurnLogPrinter, "close", ...)` で `OSError("printer")` を出す、`run_app(Args(p, "none"))` | `OSError("printer")` が `run` から伝わる(警告にならない)。`err` に `warning:` も `summary:` もない | close警告 3(stdout に書けないことは隠さない) |

### Application のグラフィカル(`tests/test_app_graphical.py`、ヘッドレス・pygame が無ければ skip)

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定/仕様 |
|---|---|---|---|---|
| AG01 | graphical / both でも stdout は同じ | `headless`。パラメタライズ: `Args(p, "graphical", delay=0)` / `Args(p, "both", delay=0)` で `run_app` | `out == LOG`(AA01・AA02 と同一 → 4モードで同一)。`err` の最後の行が `SUMMARY`。`wait_for_quit` のスパイが1回呼ばれた(`hold_final=True` で最後の画面を待つ配線)。both の `err` には `=== Turn 0 (start)` もある | ログ 3(4モードでバイト単位で同じ)、可視化方針 3(`hold_final=True`)。stdout に pygame の案内文が混ざらないことの一部(import 時の案内文は Stage 7 のサブプロセスのテストで見ている) |
| AG02 | グラフィカルの組み立て | `headless`、`TtyStringIO` の stdin。パラメタライズ: ① `Args(p, "graphical", delay=0.25, step=True)` ② `Args(p, "graphical")` ③ `Args(p, "both", step=True)`。`_make_views()` だけ呼ぶ | ① `names == ["graphical"]`、`GraphicalVisualizer` で `delay == 0.25`、`step is True`、`hold_final is True`、`is_open is False`(構築では窓を開かない) ② `delay == 0.5`、`step is False` ③ `names == ["terminal", "graphical"]`(この順)、ターミナルの `step is False`(入力は端末なのに)、グラフィカルの `step is True` | ステップ(both ではグラフィカルだけが進行を握る)、CLI形 5(常に `hold_final=True`)。ターミナルが先に並ぶこと |
| AG03 | 窓が開けない → `VisualizationError` | `SDL_VIDEODRIVER=nosuch`(`headless` は使わない)。パラメタライズ: `graphical` / `both`。both は `TerminalVisualizer.close` をスパイ(元の close を呼ぶ)に差し替え | `VisualizationError`、`str(exc).startswith("cannot open the graphical window: ")`。`out == ""`。both では `err` に `=== Turn 0 (start)`(ターミナルの begin は先に済んでいる)があり、ターミナルの `close` が1回呼ばれた。`summary:` はない | エラー 4、S7点 2(begin の失敗でも close。both でターミナル側の後始末が走る) |
| AG04 | main での窓のエラー | `SDL_VIDEODRIVER=nosuch`、`call_main(p, "--visual", "graphical")`(`tests/test_fly_in.py` のヘルパーと同じものをこのファイルに置く) | 戻り値 1。`capsys` の `err` が `error: cannot open the graphical window: ` で始まる1行だけ、`out == ""`。`Traceback` を含まない | エラー 4 を main の終了コードまで通す |

### main の例外表(`tests/test_fly_in.py`、pygame 不要)

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定/仕様 |
|---|---|---|---|---|
| AM01 | 正常終了 | `call_main(p, "--visual", "none")` | 戻り値 0。`capsys` の `out == LOG`、`err == SUMMARY + "\n"`(`main` は既定の `sys.stdout` / `sys.stderr` を使う) | ゴール 1・2、`Application` の既定の出力先 |
| AM02 | `FlyInError` → `error: ...` と 1 | パラメタライズ: ① 存在しない `tmp_path/"no_such.txt"` ② AA07 ① のマップ ③ AA07 ② のマップ、いずれも `--visual none` | 戻り値 1。`err` がちょうど1行: ① `error: cannot read map file '<str(path)>': No such file or directory` ② `error: line 1: the first line must be 'nb_drones: <n>'` ③ `error: goal 'g' is unreachable from 's'`。`out == ""` | エラー 1・2。トレースバックなしの1行 |
| AM03 | 引数の誤りは 2、`Application` を作らない | `RaisingApp` を「構築されたら失敗」するスタブにする。`call_main("m.txt", "--delay", "-1")` | `pytest.raises(SystemExit)` で code 2。スタブは構築されない。`err` に `usage:` | CLI形 3(マップや実行のエラーの1と分ける)。引数の検査が最初 |
| AM04 | Ctrl+C → `error: interrupted` と 130 | `RaisingApp(KeyboardInterrupt())` | 戻り値 130(`EXIT_INTERRUPTED`)。`err == "error: interrupted\n"` | エラー 6 |
| AM05 | 実行中の Ctrl+C(本物の経路) | `TurnLogPrinter.render` を、3回目の呼び出しで `KeyboardInterrupt` を出すように包む(2回目までは元の render)。`call_main(p)`(terminal)。`TerminalVisualizer.close` をスパイ | 戻り値 130。`out` が `LOG` の最初の2行。`err` の最後の行が `error: interrupted`、`summary:` がない。ターミナルの `close` が1回呼ばれた | エラー 6(ビューはエンジンの `finally` で閉じる)。`_GuardedView` は `KeyboardInterrupt` を受けない |
| AM06 | パイプが閉じた → 何も出さずに 1 | `silenced`。パラメタライズ: ① `RaisingApp(BrokenPipeError())` ② `RaisingApp(OSError(errno.EINVAL, "Invalid argument"))` を **Windows のときだけ**(`skipif(os.name != "nt")`)③ 本物の経路: `sys.stdout` を `write` で `BrokenPipeError` を出す `StringIO` の派生に `monkeypatch.setattr(sys, "stdout", ...)`(capsys は使わない)して `call_main(p, "--visual", "none")` | 戻り値 1。`err == ""`(capsys / capfd の stderr)。`_silence_stdout` のスパイが1回呼ばれた。③ では `summary:` も出ない | エラー 7、`docs/bugs.md` 2026-10-18(Windows の EINVAL) |
| AM07 | `_is_closed_pipe` の判定表 | `fly_in._is_closed_pipe` を直接呼ぶ。`monkeypatch.setattr(fly_in.os, "name", ...)` で `"nt"` / `"posix"` を切り替える(呼び出しの間だけ。確認したい点 4) | `BrokenPipeError()` は両方で True。`OSError(errno.EINVAL, ...)` は nt で True・posix で False。`OSError(errno.ENOENT, ...)`、`PermissionError()`、`errno` なしの `OSError("x")` は両方で False | エラー 7(EINVAL は Windows だけ。ほかの OSError を飲み込まない) |
| AM08 | 予期しない例外は最後の砦で1行 | `silenced`。パラメタライズ: ① `RaisingApp(ValueError("injected bug"))` ② `RaisingApp(PermissionError("denied"))`(パイプでない OSError は `_run` が再送出) ③ AA10 の import の失敗(`call_main(p, "--visual", "graphical")`) | 戻り値 1。`err` がちょうど1行: ① `error: internal error: ValueError: injected bug` ② `error: internal error: PermissionError: denied` ③ `error: internal error: ModuleNotFoundError: ` で始まる。`Traceback` を含まない。`_silence_stdout` は呼ばれない | 最後の砦 1(既知の扱いの外、パイプ以外の OSError もここ) |
| AM09 | `FLYIN_DEBUG` | パラメタライズ: ① `FLYIN_DEBUG=1` で `RaisingApp(ValueError("x"))` ② 同じく `"0"` / `"true"` / `""` ③ `FLYIN_DEBUG=1` で `RaisingApp(ParseError(1, "bad"))` と `RaisingApp(KeyboardInterrupt())` | ① `pytest.raises(ValueError)`(同じオブジェクトが伝わる) ② 戻り値 1 と internal error の1行(`"1"` のときだけ送出) ③ それぞれ `error: line 1: bad`・1 と `error: interrupted`・130(既知の扱いは変わらない) | 最後の砦 2・3(`make debug` は `FLYIN_DEBUG=1` で pdb に渡す。`KeyboardInterrupt` は `Exception` でない) |
| AM10 | close の失敗と終了コード(main) | `fail_close`。① `call_main(p)` ② `StuckScheduler(ok_turns=0)` も差し替えて `call_main(p)` | ① 戻り値 0、`err` の最後の2行が `warning: could not close the terminal view: boom` と `SUMMARY` ② 戻り値 1、`err` の最後の2行が `warning: ...: boom` と `error: turn 1: no drone moved, so the simulation cannot progress`(警告が先、元のエラーが後) | close警告 2(成功を失敗と報告しない、失敗では元のエラーを出す。順序) |

### サブプロセスの E2E(`tests/test_fly_in.py`、2回だけ)

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定/仕様 |
|---|---|---|---|---|
| AE01 | 本当のプロセスでの正常終了 | `run_script("maps/subject_example.txt")`(既定の terminal、stdin は DEVNULL) | `returncode == 0`。`stdout.splitlines() == subject_output`。`stderr` の最後の行が `SUMMARY`、`Traceback` を含まない。stdout に `pygame` / `===` を含まない | ゴール 1・2、既定マップ(`maps/subject_example.txt` が課題の例と同じ内容で、`make run` の既定として成功すること)、`if __name__ == "__main__"` の配線 |
| AE02 | 本当のプロセスでのエラー | `run_script("no_such_map.txt", "--visual", "none")` | `returncode == 1`。`stderr == "error: cannot read map file 'no_such_map.txt': No such file or directory\n"`(1行だけ)。`stdout == ""` | エラー 2、「トレースバックを出さない」を本当の終了まで確かめる |

ケース数: AC 8 + AP 4 + AS 3 + AA 14 + AG 4 + AM 10 + AE 2 = **45 件**(パラメタライズを展開すると約 90 件の実行)。

## 手動で確認すること(単体テストにしない)

- **Makefile**(`make install` / `run` / `debug` / `clean` / `fclean` / `lint` / `lint-strict` / `test`): `make` のある Linux / macOS
  (採点環境)で、`.venv` なしの状態から順に実行する。`make run MAP=... ARGS="--visual none"`、`.venv/.installed` が
  `requirements.txt` より古いときの再インストール、`make clean` が `.venv` の中を消さないこと、`make lint` が課題 III.2 の
  フラグそのままで通ること。開発機には `make` がなく未確認(decisions.md「Makefile / …」)なので、最初の確認を兼ねる。
- `make debug` で例外を差し込み、pdb の post mortem に入ること(`FLYIN_DEBUG=1` の配線。単体では AM09 で環境変数の効き方だけ見る)。
- 本物のパイプ: `python fly_in.py maps/subject_example.txt --visual none | head -1` が、POSIX と Windows の両方で
  トレースバックも `Exception ignored ...` も出さずに終わること(`_silence_stdout` の `os.dup2` は単体ではスパイに差し替えている)。
  7行は小さくパイプのバッファに収まるため、サブプロセスでの自動化は確実に再現できないので見送る。
- 本物の Ctrl+C(ターミナルの `--step` の待ち、グラフィカルの最後の画面の待ちの最中)で `error: interrupted`・130 になること。
- 画面のある環境での `--visual graphical` / `both` / `--step`(右矢印・Esc)。
- pygame を入れていない環境(`.venv` なし)で `--visual terminal` / `none` が動き、`graphical` が案内文の1行で終わること(AA08 の実地確認)。

## 作成フェーズへの申し送り

1. `fly_in._silence_stdout` は、`fly_in.main` を呼ぶテストでは**常にスパイに差し替える**(AM06 以外で誤って呼ばれても
   テストのプロセスの stdout を壊さないように)。`silenced` を `tests/test_fly_in.py` の autouse にしてよい。
2. `FLYIN_DEBUG` は autouse で消してから、必要なケースだけ設定する。
3. `TerminalVisualizer` は `sys.stdin` を**構築時**に読む。AA04・AG02 は `sys.stdin` を差し替えてから `Application._make_views()` を呼ぶ。
4. `no_pygame` の後に `graphical_view` を import し直すテスト(AG 系)と同じプロセスで走っても、`monkeypatch` が `sys.modules` を
   元に戻すので影響しない。ただし `test_app.py` の中で `graphical_view` を直接 import しない(`no_pygame` の前に読み込まれると
   AA05 の判定が変わる。AA05 は事前に `delitem` する)。
5. AE01・AE02 は `cwd` をリポジトリ直下(`Path(__file__).resolve().parents[1]`)にし、`env` から `FLYIN_DEBUG` を除く。
   Windows の改行(`\r\n`)に備えて `text=True` と `splitlines()` で比べる。`timeout` を付ける。
6. AG 系は `delay=0`(`Args` で直接)、`wait_for_quit` のスパイ、番犬を併用する。経過時間のアサーションは書かない。
7. ディレクトリの理由(AA06 ②)と `OSError` の文言は OS で違うので、プレフィックスと「空でない」だけを見る。
8. `flake8` と `mypy --strict`(`make lint-strict` は `tests/` も対象)を通す。内部名(`_make_views` / `_GuardedView` / `_Window` /
   `_is_closed_pipe` / `_silence_stdout`)への依存は Stage 7 と同じく許容する(確認したい点 1)。
9. 作成後、`tests/README.md` のカバレッジ欄に追記する(テストフォルダごとの README は共通ルール)。

## 設計中に見つけた実装の問題(`docs/bugs.md` に記録、コードは変更していない)

1. **大きな `--delay` がグラフィカル表示で `OverflowError` になる**(`droneflow/visualization/graphical_view.py:208`)。
   `--delay 1e308` は `_delay` の検査(有限・0 以上)を通るが、`_Window.wait` の `int(self.delay * 1000)` で
   `delay * 1000` が `inf` になり、`error: internal error: OverflowError: cannot convert float infinity to integer`・終了コード1で終わる
   (`SDL_VIDEODRIVER=dummy` で再現)。上下の矢印での変更は `_MAX_DELAY`(5秒)で頭打ちにしているが、起動時の値は頭打ちにしていない。
   直し方の候補(ユーザー判断): `--delay` に上限を設ける(例: `_MAX_DELAY` と同じ5秒、または 1 日など)/ `GraphicalVisualizer` が
   受け取った値を `_MAX_DELAY` で頭打ちにする / `_delay` で `value * 1000` が有限であることも検査する。
   決まったら AC05 に拒否する値(または AG に頭打ちの値)を1件足す。
2. **マップのパスが「書かれたとおり」に出ない**(`droneflow/cli.py:50` の `type=Path` と `droneflow/app.py:120` の `str(path)`)。
   `MapFileError.path` の docstring は「as given on the command line」、コミット c9f48eb は「show map paths as given」だが、
   `pathlib.Path` が正規化するため、`./maps/none.txt` や `maps//none.txt` は `maps/none.txt` に、Windows では
   `maps\none.txt` になって表示される。理解の妨げは小さいので軽微。直し方の候補: `Args.map_path` を `str` で持つ、または
   `Application` が `MapFileError` に元の文字列を渡す。AE02 / AM02 は正規化の影響を受けないパス(`no_such_map.txt`、
   `str(tmp_path / ...)`)を使うので、どちらに決まっても通る。決まったら AM02 に `./` 付きのケースを足すかを決める。

## 確認したい点の決定(2026-10-18、ユーザー判断)

1. 内部名への依存: **このままでよい**(`_make_views` / `_GuardedView` / `_is_closed_pipe` / `_silence_stdout` を使う)。
2. `TtyStringIO`: **`tests/conftest.py` に上げて共有する**(`tests/visualization/conftest.py` から移す。作成フェーズで行う)。
3. `main(argv=None)`: **追加した**(291c37c)。`fly_in.main(["m.txt", ...])` で呼べる。`sys.argv` の差し替えは不要。
4. AM07: **`monkeypatch.setattr(fly_in.os, "name", ...)` で切り替えてよい**(monkeypatch で元に戻すこと)。
5. ワークフロー文書の1行目の記述: **直した**(`D1-corridorA`)。
6. 問題 1・2: **直した**(`docs/bugs.md` 参照)。追加するケース:

| ID | 対象 | セットアップ | 期待結果 | 意義・守る決定/仕様 |
|---|---|---|---|---|
| AC09 | `--delay` の上限 | パラメタライズ: `"60"` → 受理(60.0)、`"60.5"` / `"1e308"` → 拒否 | 受理は `args.delay == 60.0`。拒否は `SystemExit` code 2、stderr の最後の行が `fly_in.py: error: argument --delay: must be between 0 and 60 seconds: '60.5'`(`'1e308'`) | 問題 1(上限 60 秒、usage エラー)。60 ちょうどは受理(境界) |
| AA09 | マップのパスは書かれたとおり | `Args` を `parse_args(["./" + 存在しない名前, "--visual", "none"])` で作り、`run_app`(または `call_main`)。名前には `//` も含める(例: `./no_such//map.txt`) | `MapFileError` の `str(exc)`(main なら `err` の1行)が `cannot read map file './no_such//map.txt': ` で始まる。あわせて `parse_args(["./m.txt"]) == parse_args(["m.txt"])`(`map_arg` は比較に使わない)、`.map_name == "./m.txt"` | 問題 2(表示は入力どおり、I/O は `Path`) |

(AC01 の `Args(...)` との比較は、`map_arg` が `compare=False` なのでそのまま通る。`GraphicalVisualizer(delay=1e308).delay == 60.0`
の頭打ちは、必要なら Stage 7 のテストに1件足してよい。)

## 確認したい点(設計時の記録)


1. **内部名への依存**: AA04・AA05・AG02 は `Application._make_views()` と `_GuardedView.name` / `.view` を、AM06〜AM08 は
   `fly_in._silence_stdout` / `_is_closed_pipe` を使う。Stage 7 と同じく内部名のまま使う(推奨。コード変更なし)か、
   ビューの組み立てを公開名(例: `Application.make_views()`)にするか。
2. **`TtyStringIO` の置き場所**: `tests/visualization/conftest.py` にある同じクラスを、`tests/conftest.py` に上げて共有する
   (推奨。意味は変えない)か、`tests/test_app.py` に複製するか。
3. **`main(argv=None)` にするか**: 今は `sys.argv` を `monkeypatch` で差し替える(コード変更なし)。`parse_args` は `argv` を
   受けるので、`main` も受けるようにすればテストが素直になる(任意)。
4. **AM07 の `os.name` の差し替え**: `fly_in.os` は標準の `os` そのものなので、`monkeypatch.setattr(fly_in.os, "name", "posix")` は
   呼び出しの間だけプロセス全体の `os.name` を変える(`_is_closed_pipe` だけを呼ぶので実害はない想定)。代わりに
   `skipif` で今の OS の分岐だけを見る案もある(どちらの OS でも片側しか見られない)。前者でよいか。
5. **ワークフロー文書の古い記述**: `docs/research/2026-10-18_workflow-cli-app.md` の完了条件に「課題の例で `D1-roof1 D2-corridorA`
   で始まる7行」とあるが、実際の(そして `subject_output` の)1行目は `D1-corridorA`(2026-10-17 の判断の順序の決定以降)。
   挙動図の例の行も同様。文書の誤りでコードは正しいと考えるが、直してよいか。
6. **設計中に見つけた問題 1・2** の扱い(上記)。
