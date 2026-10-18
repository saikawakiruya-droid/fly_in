# バグ記録(Bug Log)

実装中に発生したバグ・不具合の発生箇所をここに記録していく。
レビュー前後に必ず参照すること。

フォーマット:

```
## YYYY-MM-DD: <症状の見出し>
- 発生箇所: <ファイル>:<行>
- 症状:
- 原因:
- 対応状況: 未対応 / 対応中 / 対応済み(コミット等の参照)
```

---

## 2026-09-17: Drone.current_zone の型ヒントとdocstringの不整合

- 発生箇所: `droneflow/models/drone.py:20`(docstring)/`:32`(型ヒント)
- 症状: docstringには「IN_TRANSIT中はNoneになる」と明記されているのに、
  型ヒントは `current_zone: str`(Optionalでない)になっていた。mypy --strictの下で
  IN_TRANSIT中に `current_zone = None` を代入するコードを書くと型エラーになる。
- 原因: スケルトン作成時にdocstringと型ヒントが同期していなかった。
- 対応状況: 対応済み。型ヒントを `current_zone: str | None` に修正し、docstringと一致させた。

## 2026-09-17: MapParserが通常hubのmax_drones省略時にNoneを返していた

- 発生箇所: `droneflow/parsing/map_parser.py`(`_parse_zone_line`)
- 症状: `hub:` 行で `max_drones=` メタデータを省略した場合、`Zone.max_drones` が `None`
  (無制限)になってしまっていた。
- 原因: `docs/research/2026-09-05_parser-requirements.md` に記載の
  「`max_drones=<number>`(既定値1)」を実装時に見落とし、start/end hub用の
  「省略時はNoneに正規化する」ロジック(`docs/decisions.md` 2026-09-17決定)と混同した。
  通常hubの既定値は1であり、Noneはstart/end hub専用の扱い。
- 対応状況: 対応済み。通常hubで `max_drones` 省略時は `1` を、指定時はその正整数値を使うよう修正。
  start/end hubのみ常に `None` に正規化する既存ロジックはそのまま維持。

## 2026-10-04: MapParserが `hub` のようなコロンなしのキーワードだけの行で例外を起こしていた

- 発生箇所: 分割前の `droneflow/parsing/map_parser.py`(`_parse_line` → `_parse_zone_line`)
- 症状: `hub` とだけ書かれた行で、`ParseError` ではなく `ValueError`(`line.split(":", 1)` の
  アンパック失敗)が送出され、行番号つきのエラーにならなかった。
- 原因: キーワード判定が `line.split(":", 1)[0]` だけで、コロンの有無を確認していなかった。
- 対応状況: 対応済み。分割後の `LineTokenizer.tokenize` はコロンの有無を `partition` で確認し、
  無ければ `unrecognized line` の `ParseError` にする(`tests/parsing/test_map_parser.py` に追加)。

## 2026-10-04: 分割中の `UniqueConnection` が自己ループを重複と誤判定していた

- 発生箇所: `droneflow/parsing/map_rules.py`(`UniqueConnection.check`)。コミット前の実装中に発見。
- 症状: すでに `a-b` がある状態で `a-a`(自己ループ)を宣言すると、重複として拒否された。
- 原因: 重複判定に `existing.involves(zone_b)` を使い、`zone_a == zone_b` のとき
  `zone_a` に接する任意の接続が当てはまってしまった。
- 対応状況: 対応済み。`existing.other_end(zone_a) == zone_b` で判定するよう変更。
  `tests/parsing/test_map_rules.py` に再発防止テストあり。

## 2026-10-16: 1行目がコメントのマップ(配布マップ10枚すべて)を `nb_drones` 欠落として拒否する

- 発生箇所: `droneflow/parsing/map_parser.py`(`parse` の `src.number == 1` 分岐)/
  `droneflow/parsing/line_tokenizer.py`(`tokenize_header`)
- 症状: `# Easy Level 1: ...` のように1行目がコメントのマップで
  `line 1: the first line must be 'nb_drones: <n>'` の `ParseError` になる。配布マップ10枚すべてが該当。
- 原因: 「1行目」を物理的な1行目と扱っているため。
- 対応状況: **バグではなく仕様**(対応不要)。「ファイルの物理的な1行目が `nb_drones:` でなければエラー」を
  正式な方針とした(decisions.md 2026-10-16)。`revie_case/maps/parse_error/E35_comment_first_line.txt` で確認する。

## 2026-10-16: 空ファイルのエラーメッセージの行番号が `line 0` になる

- 発生箇所: 空ファイル時の `ParseError`(`MapParser.parse` 周辺。`revie_case/maps/parse_error/E32_empty_file.txt` で再現)
- 症状: `line 0: map file is empty, ...` と表示される。行番号は1始まりなので `0` は利用者に分かりにくい。
- 原因: 未調査(空ファイル用に行番号0を渡している)。
- 対応状況: 未対応(軽微。メッセージ自体は明確なので評価上の影響は小さい)。

## 2026-10-16: メタデータの重複キーが後勝ちになり、start/end の `zone=blocked` 検査をすり抜ける

- 発生箇所: `droneflow/parsing/line_tokenizer.py:93`(`LineTokenizer._split_metadata` のキー登録部分。修正前は `metadata[key] = value` で上書き)
- 症状: `start_hub: s 0 0 [zone=blocked zone=normal]` のように同じ行で同じキーを2回書くと、後ろの値だけが残り
  エラーにならない。start/end の禁止オプション(`zone=blocked`)の検査を、後ろに `zone=normal` を足すだけで回避できた
  (逆順 `[zone=normal zone=blocked]` はエラーになる)。`[max_link_capacity=1 max_link_capacity=2]` なども黙って後勝ちになる。
- 原因: メタデータを dict に詰める際に、既に同じキーがあるかを確認していなかった。
- 対応状況: 対応済み(`fix/duplicate_metadata_key`、コミット 62388bd)。tokenizer(構文段階)で重複キーを検出し、
  `line N: duplicate metadata key 'zone'` の `ParseError` にする(decisions.md 2026-10-16「メタデータの重複キーは `ParseError` にし…」)。
  単体テスト追加済み(`test/duplicate_metadata_key`): `tests/parsing/test_line_tokenizer.py` の T01〜T04、
  `tests/parsing/test_map_parser.py` の M01〜M03(docstring は「Duplicate key M0x」)。設計は
  `docs/research/2026-10-16_test-design-duplicate-metadata-key.md`。

## 2026-10-18: `CompositeVisualizer.close` が、先に失敗したビューの例外を失う

- 発生箇所: `droneflow/visualization/composite.py:36`(`close` の `ExitStack`)
- 症状: 複数のビューの `close` が失敗すると、最後の例外だけが送出され、その `__context__` は `None` になる。docstring の
  「the last failure is raised, with the earlier ones chained to it as context」と食い違い、先に失敗したビューの例外が失われる。
  全ビューを閉じる点(1つが失敗しても残りを閉じる)は正しく動いている。
- 原因: `with` の本体で例外が起きていないとき、`ExitStack` はコールバック同士の例外をつながない(CPython の
  `ExitStack._fix_exception_context` は、新しい例外の `__context__` が `None` のとき何もしない)。設計時に Python 3.14.6 で確認。
- 対応状況: 対応済み(b06e2c9)。docstring どおりに実装を直した。`ExitStack` をやめ、ビューを順に `try/finally` の入れ子
  (`_close_from` の再帰)で閉じる。後のビューの `close` が前の失敗の処理中に送出されるので、Python が `__context__` を
  自動でつなぐ。テスト設計の VC03 は `xfail` を外して通常のケースにした。

## 2026-10-18: ステップ実行のグラフィカル表示で、最後のターンでも右矢印を待つ(要確認)

- 発生箇所: `droneflow/visualization/graphical_view.py:546`(`GraphicalVisualizer._show` の `window.wait()`)
- 症状: `step=True` では、全機が配達済みになった最後のフレームでも一時停止のまま待つ。`hold_final=True` だと
  「右矢印 → finished の表示 → Esc」の2段階になり、finished の表示は右矢印を押すまで出ない。ターミナルのステップ実行は
  最後のターンの後に待たないので、両者の振る舞いがそろっていない。
- 原因: `_show` が `state.is_complete` を見ずに毎回 `wait()` を呼ぶ。ステップ実行の決定(2026-10-18)は、グラフィカル側の
  最後のフレームの扱いを定めていない。
- 対応状況: 対応済み(c832eb1)。バグとして扱い、最後のフレーム(全機配達済み)では、一時停止中(ステップ実行)または
  `hold_final=True` のとき `wait()` を呼ばないようにした。`hold_final=True` なら `close()` が finished の表示で閉じる操作を待つ。
  決定は `docs/decisions.md` 2026-10-18「Stage 7 のテスト設計で挙がった点の扱い」。テスト設計に VG17 を追加した。

## 2026-10-18: `flake8 .` が `.venv` の中まで検査し、`mypy .` が `conftest.py` の重複で止まる

- 発生箇所: リポジトリ直下での課題 III.2 の lint コマンド(`flake8 .` / `mypy . ...`)。Makefile の作成中に発見。
- 症状: `flake8 .` が `.venv/Lib/site-packages` の中まで検査して数千件のエラーになる。`mypy .` は
  `Duplicate module named "conftest"`(`tests/pathfinding` / `tests/simulation` / `tests/visualization`)で検査の前に止まる。
- 原因: flake8 の既定の除外に `.venv` が入っていない。`tests/` の各フォルダには `__init__.py` がなく、mypy が3つの
  `conftest.py` をどれも `conftest` という名前のモジュールとして扱う。
- 対応状況: 対応済み。`setup.cfg` に `[flake8] extend-exclude = .venv,...` と `[mypy] explicit_package_bases = True` を置いた
  (decisions.md 2026-10-18「Makefile / requirements.txt / setup.cfg」)。

## 2026-10-18: `mypy . --strict` が `tests/simulation/test_turn_resolver.py:203` を誤って報告する

- 発生箇所: `tests/simulation/test_turn_resolver.py:203`(`assert drone.status is DroneStatus.AT_ZONE`)
- 症状: `make lint-strict` の `mypy . --strict` で
  `Non-overlapping identity check (left operand type: "Literal[DroneStatus.IN_TRANSIT]", ...)  [comparison-overlap]`。
- 原因: 直前の `assert drone.status is DroneStatus.IN_TRANSIT` で mypy が `drone.status` の型を絞り込んだまま、
  `resolver.resolve(...)` が `drone` を書き換えたことを知らない。`--strict` に含まれる `strict_equality` がこれを報告する。
  コード(`droneflow/`)の問題ではない。
- 対応状況: 対応済み(テストは変えていない)。`setup.cfg` で `tests.*` だけ `strict_equality = False` にした。
  `# type: ignore` は、`--strict` なしの `make lint`(`--warn-unused-ignores`)で「使われていない ignore」になるため使えない。

## 2026-10-18: Windows で stdout のパイプが閉じると、`BrokenPipeError` ではなく `OSError(EINVAL)` になる

- 発生箇所: `fly_in.py`(`main`)/ `droneflow/output/turn_log_view.py`(`TurnLogPrinter.render` の flush)。CLI の確認中に発見。
- 症状: 読み手が先に閉じたパイプに stdout を書くと、Windows では `OSError: [Errno 22] Invalid argument` のトレースバックと、
  終了時の `Exception ignored while flushing sys.stdout` が出た(終了コード120)。
- 原因: POSIX では `BrokenPipeError`(EPIPE)になるが、Windows では EINVAL として報告される。最初の実装は `BrokenPipeError` だけを
  受けていた。
- 対応状況: 対応済み。`_is_closed_pipe` で、`BrokenPipeError` と(Windows の場合だけ)EINVAL を「パイプが閉じた」とみなし、
  stdout を devnull に向け直して終了コード1で静かに終える。

## 2026-10-18: 大きな `--delay` がグラフィカル表示で `OverflowError` になる

- 発生箇所: `droneflow/visualization/graphical_view.py:208`(`_Window.wait` の `int(self.delay * 1000)`)。
  CLI のテスト設計(`docs/research/2026-10-18_test-design-cli-app.md`)で発見。
- 症状: `--delay 1e308` は `droneflow/cli.py` の `_delay` の検査(有限・0 以上)を通るが、`--visual graphical` / `both` で
  `error: internal error: OverflowError: cannot convert float infinity to integer`・終了コード1になる(`SDL_VIDEODRIVER=dummy` で再現)。
- 原因: `delay * 1000` が float の範囲を超えて `inf` になる。上下の矢印での変更は `_MAX_DELAY`(5秒)で頭打ちにしているが、
  起動時に渡された値は頭打ちにしていない。
- 対応状況: 対応済み(a448708、7089fe7)。ユーザー判断で両方を行った: CLI は `--delay` を 0〜60 秒に限り、60 を超えると
  argparse の usage エラー(`must be between 0 and 60 seconds: '61'`、終了コード2)。`GraphicalVisualizer` も構築時に
  delay を 0〜60 秒に頭打ちにする(NaN は 0)。矢印キーでの変更の上限 `_MAX_DELAY`(5秒)は変えていない。
  decisions.md 2026-10-18「CLI のテスト設計で見つかった点の対応」。

## 2026-10-18: マップのパスがエラーメッセージで「書かれたとおり」に出ない

- 発生箇所: `droneflow/cli.py:50`(`type=Path`)と `droneflow/app.py:120`(`MapFileError(str(path), ...)`)。
  CLI のテスト設計で発見。
- 症状: `python fly_in.py ./maps/none.txt` や `maps//none.txt` が `error: cannot read map file 'maps/none.txt': ...`
  (Windows では `'maps\none.txt'`)と表示される。`MapFileError.path` の docstring「as given on the command line」と、
  コミット c9f48eb の「show map paths as given」に食い違う。
- 原因: `pathlib.Path` が `./` や連続した `/` を正規化し、Windows では区切りを `\` にする。
- 対応状況: 対応済み(7089fe7)。`Args` に、入力どおりの文字列 `map_arg`(比較には使わない)と、それを返す `map_name` を足した。
  I/O は従来どおり `Path` の `map_path` で行い、`MapFileError` には `map_name` を渡す
  (`./maps//none.txt` は `error: cannot read map file './maps//none.txt': ...` と出る)。
  decisions.md 2026-10-18「CLI のテスト設計で見つかった点の対応」。

## 2026-10-19: 同じターン番号の別の状態を `decide_moves` に渡すと、前の状態の着陸が予約表に残る

- 発生箇所: `droneflow/simulation/scheduler.py:133-143`(`Scheduler._start_turn`)。予約表のテスト設計
  (`docs/research/2026-10-19_test-design-timed-reservation.md` の D26)で発見。
- 症状: `s-r r-g`(r は restricted・容量1)で、1つの `Scheduler` に `place(n, 2, flying={1: ("s", "r")})` を渡して
  `decide_moves` した後、同じターン番号(0)の別の状態 `place(n, 2)`(全機が s)を渡すと `[]` が返る。新しい `Scheduler` なら
  `[MoveOrder(1, "r")]`。前の状態の D1 の着陸 `(r, 1)` が表に残り、r に席がないと判断される。
- 原因: 同じターンの再呼び出しでは `rollback(self._turn_mark)`(そのターンに作った予約の取り消し)だけを行い、
  `ReservationTable.start_turn(state)`(着陸を状態から作り直す)をやり直さない。docstring の「Called again for the same turn,
  it drops the moves it planned for that turn and plans it again」は、状態が同じ前提を書いていない。
- 影響: アプリ(`droneflow/app.py:96`)は実行ごとに新しい `Scheduler` を作り、エンジンは毎ターン1回だけ呼ぶので、今の使い方では起きない。
  同じ状態での再呼び出し(D24)は正しく動く。
- 対応状況: 未対応(コードは変えていない)。直す(同じターンでも `start_turn(state)` をやり直す)か、docstring に前提を書くかはユーザー判断待ち。
