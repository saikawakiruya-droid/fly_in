# tests/

`droneflow` パッケージの単体テスト。提出・採点の対象外(課題要件・共通ルール上、任意)だが、
実装の挙動確認・リグレッション防止のために作成している。

## 位置づけ

- プロジェクト本体(`droneflow/`)から独立したディレクトリとして分離している。
  `tests/` ごと削除してもアプリケーション本体は動作する。
- ディレクトリ構成は `droneflow/` のパッケージ構成に対応させている
  (例: `droneflow/models/zone.py` のテストは `tests/models/test_zone.py`)。

## 実行方法

リポジトリルートで:

```sh
python -m pytest tests/
```

`tests/visualization/test_graphical_view.py` は pygame(pygame-ce)が必要。入っていなければこのファイルだけ skip され、
ほかのテストは pygame なしで走る。グラフィカル表示のテストはヘッドレス(`SDL_VIDEODRIVER=dummy`)で動くので、画面は要らない。

## 現在のカバレッジ範囲

- `tests/models/test_zone.py` — `ZoneType.turn_cost` / `is_traversable`、
  `Zone.has_unlimited_capacity`
- `tests/models/test_connection.py` — `Connection.involves` / `other_end`、`Connection.name`
  (宣言どおりの `zone_a-zone_b` で並べ替えない)
- `tests/models/test_drone.py` — `Drone.is_delivered`、`Drone.transit_target`(既定は `None`・飛行中は値を保持)
- `tests/models/test_network.py` — `Network` の登録・検索・隣接・start/end取得と、
  それぞれの例外契約(`ZoneNotFoundError` / `SimulationError`)、`connection_between`
  (両方向で同じ接続・つながっていない/存在しない名前は `None`・同じ名前2つで自己ループ)
- `tests/test_errors.py` — `ZoneNotFoundError` の例外階層・属性、`UnreachableGoalError` の例外階層
  (`FlyInError` の子で `ParseError` / `SimulationError` とは別)・属性・行番号なしのメッセージ
- `tests/parsing/test_map_parser.py` — `MapParser`(章VII.4のパーサ制約全般):
  仕様書記載のサンプルマップの正常系パース、メタデータ省略時のデフォルト値
  (zone/color/max_drones/max_link_capacity)、start/end hubのmax_drones正規化、
  重複(ゾーン名・接続・start/end hub)の即時検出、start/end hub欠落、不正な
  ゾーンタイプ・メタデータキー・メタデータ構文・座標・ゾーン名、未定義ゾーンへの
  接続参照、空ファイル、自己ループ接続・座標重複の許容(いずれもParseErrorにしない)、
  start/end hubの禁止オプション(`zone=blocked` は行番号つきの ParseError。コメント・空行を挟んだ
  物理行番号、他のメタデータとの組み合わせ・書き順、普通の hub の blocked と start/end の他の
  ゾーンタイプは許容、以前は経路探索で失敗したマップがパースで失敗すること)、start/end の
  max_drones は無視されるが値は正の整数でなければ ParseError、メタデータの重複キー(start/end の
  `zone=blocked` を後ろの `zone=` で隠せないこと(両方の書き順)、end_hub 側の物理行番号、重複のない
  複数キーのブロックは従来どおりパースできること)
- `tests/parsing/test_map_format.py` — 仕様表(`MapFormat`)の変換部品(整数・正の整数・
  ゾーン名・ゾーンタイプ・接続の両端)、`FieldSpec` の既定値とエラー文言、hub / start_hub /
  connection / header の組み立て(max_drones の既定値と start/end での破棄)、
  禁止オプション(`ForbiddenOption` / `LineSpec.forbidden`): 既定は空、`START_END_FORBIDDEN` が
  start_hub / end_hub の両方に付くこと(max_drones は含まない)、キーが書かれた時だけ一致すること、
  変換後の値で比べて文言には書かれたとおりの値を出すこと、変換エラーが禁止の検査より先なこと
- `tests/parsing/test_line_tokenizer.py` — `LineTokenizer` の構文検査(トークン数・括弧・
  key=value・未知キー・未知キーワード)と行番号、ヘッダー行の別扱い、メタデータの重複キー
  (全行種で拒否・同じ値の重複も拒否・不正なエントリとはトークン順で先の問題を報告・
  未知キーより重複を先に報告・キーは大文字小文字を区別)
- `tests/parsing/test_map_rules.py` — 行をまたぐ規則(ゾーン名重複・start/end重複・
  未定義ゾーンへの接続・接続重複と自己ループ)
- `tests/output/test_formatter.py` — `TurnLogFormatter`: `D<ID>-<行き先>` の空白区切り整形、
  呼び出し順の保持(ソートしない)、接続名のそのまま出力、空ターンのスキップ、`capsys` での標準出力検査

- `tests/conftest.py` — 全テスト共通のフィクスチャ: `make_network`(`"s-a a-g"` のような記述から
  `Network` をコード内で組む。記述順=接続の宣言順=接続名。hub の `max_drones` は既定 1(パーサーと同じ)で
  `capacity` で、接続の `max_link_capacity` は既定 1 で `links` で個別に指定できる。start/end は常に `None`)、
  `write_map`(`tmp_path` にマップを書く。1行目は必ず `nb_drones:`)、`load_world`(`write_map` で書いて
  `MapParser` で読んだ `World`)、`place`(検査をしない基本操作でドローンをゾーン・飛行中に置いた状態を作る)、
  `snapshot`(状態の値をコピーする)、課題のサンプルマップと期待出力(`subject_map` / `subject_output`、
  corridorA を blocked にした `restricted_only_map`)。後の4つは Stage 7 で `tests/simulation/conftest.py` から移した
  (simulation と visualization のテストで共有)

- `tests/pathfinding/conftest.py` — `grid_network`(20×20 の格子。`make_network` で組む)
- `tests/pathfinding/test_distance_map.py` — `DistanceMap`: ゾーンタイプ別の進入コスト(restricted=2・priority=1、
  restricted な end を含む)、blocked の除外と通過不可、行き止まり・孤立ゾーン、自己ループ・閉路、
  存在しない名前の `ZoneNotFoundError`、end が blocked のときの防御的な挙動、20×20 格子での距離
- `tests/pathfinding/test_pathfinder.py` — `Pathfinder`: 構築時の到達不能検出(`UnreachableGoalError`、4パターン)、
  `distance` の委譲、`next_hops` の判定(`turn_cost + 距離` で比較)・並び順(priority は次の1手の同点の中だけで先頭、
  それ以外は接続の宣言順、安定ソート)・遠回りの priority を選ばないこと・blocked の除外・空リストを返す場所、
  `best_route` の `total_cost` と `from_zone` 指定・例外の種類、経路の整合性チェック、
  パーサー経由の E2E(課題のサンプルマップ、到達不能マップはパース成功・経路探索で失敗)

- `tests/simulation/conftest.py` — スタブのスケジューラ(台本どおりの `ScriptedScheduler`、最短経路を貪欲にたどる
  `FollowerScheduler`、何もしない `IdleScheduler`、往復し続ける `OscillatingScheduler`)、
  render の呼び出しを記録する `recorder`、`begin` / `render` / `close` を呼ばれた順に1つのリストに記録し、指定した
  メソッドで失敗もできる `call_log`(Stage 7)、1ターンを出力の文字列にする `fmt`、
  Stage 5 用の `hop`(隣接する2ゾーン間の `Hop` を向きを問わず作る)・`real_scheduler`(本物の `Scheduler`)
- `tests/simulation/test_state.py` — `SimulationState`: 構築(全機が start に `AT_ZONE`)、`free_capacity`
  (start/end は `None`)、`enter_zone` の数え方、end への到着で配達済み(占有に残らない)、`enter_transit` の予約と
  接続の使用、`complete_transit` で予約が占有に置き換わること、restricted な end への到着、基本操作の前提違反
- `tests/simulation/test_turn_resolver.py` — `TurnResolver`: 出力のドローンID順(自動の到着と指示が混ざっても)、
  ゾーン容量(上限ちょうどは合法・同じターンに出ていく分は使える・3機の循環)、start/end は無制限、接続容量
  (両方向で共有・入れ替わり)、restricted の2ターン移動(出発時は宣言どおりの接続名、次ターンに自動到着・予約で満杯・
  到着のターンも接続容量に数える・飛行中への指示は拒否・restricted な end)、不正な指示(存在しないドローン/ゾーン・
  隣接していない・blocked・2つの指示・今いるゾーン)、配達済みへの指示と出力、違反後に状態が一切変わらないこと
  (到着も適用されない)とその後も続けられること、自己ループでの移動の拒否(normal / restricted)、戻り値が `Move` であること
- `tests/simulation/test_engine.py` — `SimulationEngine`: 正常終了(空のターンなし・ID順)、render はターンの適用後に
  1回ずつ(visualizer は省略可)、誰も動かないターンの `SimulationError`、到着だけのターンは進行とみなすこと、
  ターン数の上限(振動・ちょうど上限で終わる境界)、既定の上限 `default_turn_limit`、resolver の例外が伝わり違反した
  ターンでは render しないこと、構築直後の状態、パーサー経由の E2E(課題のサンプルマップの出力7行、corridorA を
  blocked にして restricted の roof1 を通る出力12行)
- `tests/simulation/test_turn_ledger.py` — `TurnLedger`: ゾーン・接続の両方の空き、ゾーン容量の境界(上限ちょうどまで)、
  記録した退出だけが同じターンの空きになること(記録前の退出は数えない=保守的)、start/end は無制限、
  restricted の予約で満杯になること、飛行中の機が接続を使うこと(到着のターンも数える)とその使用数と記録の合算、
  接続は両方向で共有、記録が他の接続・ゾーンに漏れないこと、台帳が状態を変えないこと
- `tests/simulation/test_scheduler.py` — `Scheduler`: 判断の順序(距離が近い順 → 優先ルート → drone_id。並びを
  リストの順序ごと検査)、退出で空いたゾーンを同じターンに後ろの機が使うこと、`is_on_priority_route`(今いるゾーン・
  次の一手が priority なら True、2手先・遠回りの priority・end は False、存在しない名前の `ZoneNotFoundError`)、
  遠回りせず待つこと、先頭の候補のゾーン/接続が満杯なら次の最短候補、飛行中・配達済みの機には指示しないこと、
  restricted への指示はゾーン名、restricted な end は接続容量だけで止まること、end に届かないゾーンにいる機の
  `SimulationError`、状態を変えず指示が `TurnResolver` に受理されること
- `tests/simulation/test_scheduler_maps.py` — 本物の `Scheduler` の E2E: 課題のサンプルマップの出力7行と完全一致、
  restricted だけの経路の出力12行、毎ターンの不変条件(1機1指示・指示は `AT_ZONE` の機だけ・最短の一手で距離が減る・
  resolver が受理・誰かが動く・既定の上限内)を課題の例と配布マップ10枚で確認、配布マップのターン数(VII.7 の目標以内、
  challenger は IX の45ターン未満)、アーカイブの中身、決定的であること、1機の最短距離を下回らないこと。
  配布マップはリポジトリ直下の `maps.tar.gz`(git 管理)を `tarfile` でメモリ上で読み、先頭のコメント行・空行だけを
  取り除く(アーカイブが無ければ分かりやすいメッセージで失敗する。skip にはしない)

- `tests/simulation/test_engine_hooks.py` — `SimulationEngine.run` が可視化を呼ぶ契約(Stage 7): `begin` は1ターン目の前に
  1回(ターン0・全機が start)、`render` は毎ターンそのターンの `moves` で、`close` は最後に1回。`SimulationError`
  (誰も動かない・ターン数の上限・不正な指示)、`begin` の失敗、`render` の失敗のどれでも `close` を呼び、例外はそのまま伝わること

- `tests/visualization/conftest.py` — `tty_stream`(`isatty()` が True の `StringIO`。端末の代わり)、
  `coord_network`(座標と色つきでゾーンを登録する。最初が start、最後が end)
- `tests/visualization/test_palette.py` — `rgb`: 表の値(似た赤を区別)・全エントリが 0〜255 の3つ組、大文字小文字を
  区別しないこと、配布マップ(`maps.tar.gz`)の色名17種のうち `rainbow` 以外がすべて表にあること、知らない名前・空・`None` は
  `None`、エンジン・ターミナル表示・composite・palette を import しても pygame が読まれないこと(サブプロセス)
- `tests/visualization/test_composite.py` — `CompositeVisualizer`: 呼び出しをビューの順に配る(同じ `state` / `moves`)、
  1つの close が失敗しても残りを閉じる、複数の失敗は最後を送出し前の失敗を `__context__` でつなぐ、ビューなし、
  render の失敗はそのまま伝わる
- `tests/visualization/test_terminal_view.py` — `TerminalVisualizer`: 既定の出力先が stderr(stdout は空)、begin の見出し・
  凡例・ゾーンの表・`drones:`、`frame` は書かずに行を返し render がそれを書くこと、restricted(接続名・予約 `+1`・飛行中)・
  blocked(`--`)・end(配達数)の表示、ドローンIDの範囲表記、幅での折り返しと長い名前の省略、色の強制 on/off・自動判定
  (端末かどうか・`NO_COLOR` は空でない値のときだけ)、知らない色・色なしは塗らない、close は flush するだけ、
  ステップ実行(最後のターン以外で Enter を待つ・端末でない入力や `step=False` では読まない・EOF で以後待たない)、
  状態を変えないこと、課題のサンプルマップの E2E
- `tests/visualization/test_graphical_view.py` — `GraphicalVisualizer` をヘッドレス(`SDL_VIDEODRIVER=dummy`)で:
  構築では窓を開かない、begin で開き close で閉じる、`_Layout` の座標変換(y は上向き・縮退した配置)、`zone_rgb` の
  色の引き方、課題のサンプルマップ・restricted だけのマップを最後まで描いて閉じる、途中で閉じても(×・Esc・q)計算は続く、
  ステップ実行(一時停止で始まる・右矢印で1ターン・Space で自動再生・最後のフレームは待たない)、上下の矢印での待ち時間の
  変更と上下限、close は何度でも・close の後は窓を開かない、`hold_final` の最後の画面での待ちと待たない場合、マウスでの
  詳細表示、import で stdout に何も出ないこと(サブプロセス)。pygame が無ければファイルごと skip。入力イベントは
  呼び出しの前に積み、番犬のタイマー(QUIT)でハングを防ぐ。実時間の sleep や経過時間のアサーションは使わない

対象はStage 1(Domain Model)・Stage 2(Parser & Validation)・Stage 3(Pathfinding)・Stage 4(Simulation Engine)・
Stage 5(Multi-Drone Scheduler)・Stage 6(Output Formatter)・Stage 7(Visualization)。以降のステージの実装が進み次第、対応するテストを追加していく想定。
