# tests/

リポジトリ直下のソースファイル(`*.py`)の単体テスト。提出・採点の対象外(課題要件・共通ルール上、任意)だが、
実装の挙動確認・リグレッション防止のために作成している。

## 位置づけ

- プロジェクト本体(リポジトリ直下の `*.py`)から独立したディレクトリとして分離している。
  `tests/` ごと削除してもアプリケーション本体は動作する。
- ソースはすべて直下にあるが、テストは役割ごとのフォルダに分けている
  (例: `world.py` の `Zone` のテストは `tests/models/test_zone.py`、`pathfinder.py` の `FlowMap` の
  テストは `tests/pathfinding/test_flow_map.py`)。

## 実行方法

リポジトリルートで:

```sh
python -m pytest tests/
```

## 現在のカバレッジ範囲

- `tests/models/test_zone.py` — `ZoneType.turn_cost` / `is_traversable`、
  `Zone.has_unlimited_capacity`、`Zone.capacity`(hub は `max_drones` そのまま・start/end は `None`)・
  `Zone.arrival_turn`(restricted だけ出発の次のターン。blocked でも例外にしない)・`Zone` / `Connection` / `World` が
  frozen なこと(ZC01〜ZC04)
- `tests/models/test_connection.py` — `Connection.involves` / `other_end`、`Connection.name`
  (宣言どおりの `zone_a-zone_b` で並べ替えない)
- `tests/models/test_drone.py` — `Drone.is_delivered`、`Drone.transit_target`(既定は `None`・飛行中は値を保持)、`Drone.history`(DH01: 既定は空のリストで、機ごとに別のリスト)
- `tests/models/test_network.py` — `Network` の登録・検索・隣接・start/end取得と、
  それぞれの例外契約(`ZoneNotFoundError` / `SimulationError`)、`connection_between`
  (両方向で同じ接続・つながっていない/存在しない名前は `None`・同じ名前2つで自己ループ)、
  読み取り専用のビュー(NW01〜NW03: `zones` は宣言順の `MappingProxyType` で後から足したゾーンも見える生きたビュー、
  `connections` と `neighbors` はタプルで受け取った後に変わらない)、`connection_named`(NW04: 両端から同じ接続・
  ゾーンに触れない/存在しない名前は `SimulationError`)
- `tests/test_errors.py` — `ZoneNotFoundError` の例外階層・属性、`UnreachableGoalError` の例外階層
  (`FlyInError` の子で `ParseError` / `SimulationError` とは別)・属性・行番号なしのメッセージ
- `tests/parsing/test_map_parser.py` — `MapParser`(章VII.4のパーサ制約全般):
  仕様書記載のサンプルマップの正常系パース、メタデータ省略時のデフォルト値
  (zone/color/max_drones/max_link_capacity)、start/end hubのmax_drones正規化、
  重複(ゾーン名・接続・start/end hub)の即時検出、start/end hub欠落、不正な
  ゾーンタイプ・メタデータキー・メタデータ構文・座標・ゾーン名、未定義ゾーンへの
  接続参照、空ファイルとコメント・空行だけのファイル、自己ループ接続(`a-a`)の拒否、座標重複の許容(ParseErrorにしない)、
  `nb_drones` より前のコメント・空行の読み飛ばし(後の行のエラーはファイルの行番号のまま)と、それ以外の行がある場合の
  その行の ParseError(2026-11-10 に変更)、
  BOM と改行(BM01〜BM03、2026-10-23 に変更: BOM は読み飛ばさず1行目の ParseError・CRLF のマップは LF と同じ World・
  2つ目や途中の行の BOM もその行の ParseError)、
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
  変換後の値で比べて文言には書かれたとおりの値を出すこと、変換エラーが禁止の検査より先なこと、
  `FieldValues` の型つきの読み出し(型違い・値なしは欄の名前つきの `TypeError`、`get_optional` の None)、
  `Endpoints`、builder が `FieldValues` から読むこと・仕様と builder の食い違いは `TypeError`、
  `metadata_keys` が frozenset(NT01〜NT08)
- `tests/parsing/test_line_tokenizer.py` — `LineTokenizer` の構文検査(トークン数・括弧・
  key=value・未知キー・未知キーワード)と行番号、ヘッダー行の別扱い、メタデータの重複キー
  (全行種で拒否・同じ値の重複も拒否・不正なエントリとはトークン順で先の問題を報告・
  未知キーより重複を先に報告・キーは大文字小文字を区別)、`RawLine` が tuple と Mapping(NT09)
- `tests/parsing/test_map_rules.py` — 行をまたぐ規則(ゾーン名重複・start/end重複・
  未定義ゾーンへの接続・接続重複と自己ループ)
- `tests/output/test_turn_log_formatter.py` — `TurnLogFormatter`: `D<ID>-<行き先>` の空白区切り整形、
  呼び出し順の保持(ソートしない)、接続名のそのまま出力
- `tests/output/test_turn_log_printer.py` — `TurnLogPrinter`(AP01〜AP04): begin は何も書かない・既定の出力先は stdout、
  1ターン1行で書いた直後に flush、空のターンは書かず flush もしない、close は flush だけでストリームを閉じない、
  整形は `formatter` 属性に委譲(同じ `moves` を渡す)
- `tests/output/test_summary.py` — `RunSummary`(AS01〜AS03): 課題の例の数値と文言(7ターン・5.00・2.14)、
  配達ターン=最後に出たターン(接続名の項目も1手)、ターンなし・ドローンなしでゼロ除算しないこと

- `tests/test_cli.py` — 引数(AC01・AC02・AC06〜AC08): MAP は `Path` と入力どおりの文字列(`map_name`)を持ち、既定では表示なし、
  `--terminal-view` と `--matplotlib-window` は MAP の前後どちらでもよく、両方を同時に付けられること、MAP なし・知らないオプション・
  余分な引数は終了コード2(文言まで)
- `tests/test_app.py` — `Application`: stdout が本物のスケジューラの出力(課題の例の5行。`scheduler_output`)と完全一致し、
  `--terminal-view` のときのターミナル表示と最後の要約行は stderr だけに出ること、`--terminal-view` なしでは stderr が要約行だけで
  ターミナル表示を作らないこと(AA15)、ターンの行がそのフレームより先に出ること、マップが読めない(存在しない・
  ディレクトリ・UTF-8 でない)の `MapFileError` と原因、パース・到達不能のエラーはそのまま、途中のエラーでもそれまでの
  ログとビューの後始末が残る、ターンログ側の失敗は包まない、エラーのパスは入力どおり。`make_scheduler` の注入
  (AI01: `(network, pathfinder)` で1回作りエンジンに渡す、AI02: 共有の `stuck_after` で本物の実行を途中で止める)、
  BOM つきのマップは入口で1行目の ParseError(BM04)
- `tests/test_fly_in.py` — エントリポイント: `main(argv)` の例外表(正常 0、`FlyInError` 1、引数の誤り 2 で
  `Application` を作らない、Ctrl+C 130(実行中の割り込みでもログとビューの後始末が残る)、予期しない例外は
  `internal error` の1行)。サブプロセスは2回だけ(課題の例の正常終了と、存在しないマップのエラー)

- `tests/conftest.py` — 全テスト共通のフィクスチャ: `make_network`(`"s-a a-g"` のような記述から
  `Network` をコード内で組む。記述順=接続の宣言順=接続名。hub の `max_drones` は既定 1(パーサーと同じ)で
  `capacity` で、接続の `max_link_capacity` は既定 1 で `links` で個別に指定できる。start/end は常に `None`)、
  `write_map`(`tmp_path` にマップを書く。1行目は必ず `nb_drones:`)、`load_world`(`write_map` で書いて
  `MapParser` で読んだ `World`)、`place`(検査をしない基本操作でドローンをゾーン・飛行中に置いた状態を作る)、
  `snapshot`(状態の値をコピーする)、課題のサンプルマップと期待出力(`subject_map`、課題に載っている出力例7行の
  `subject_output`、corridorA を blocked にした `restricted_only_map`)。本物のスケジューラの出力5行は `scheduler_output`
  (2機が roof1 を遠回りする。本物のスケジューラを走らせるテストはこちらを使い、`subject_output` は課題の例そのものを
  使うテスト(`test_summary.py` の AS01、`test_engine.py` の E2E)だけが使う)。後の4つは Stage 7 で `tests/simulation/conftest.py` から移した
  (simulation と visualization のテストで共有)。`tty_stream`(`isatty()` が True の `StringIO`。端末の代わり)は CLI の
  フェーズで `tests/visualization/conftest.py` から移した(visualization と Application のテストで共有)。
  `provided_map`(配布マップ `maps.tar.gz` の1枚を展開せずに、先頭のコメントも含めてそのまま読んだ文字列)と
  `maps_archive`(アーカイブを開く。無ければ分かりやすいメッセージで失敗する)は、詰まる場所の発見のテストフェーズで
  `tests/simulation/scheduling/test_scheduler_maps.py` から移した(Scheduler と詰まる場所の発見の E2E で共有)。
  `StuckScheduler` / `stuck_after`(本物の `Scheduler` に指定ターンだけ委譲し、その後は何も指示しない。
  `stuck_after(n)` を `Application(..., make_scheduler=...)` に渡す)は、全体レビューを受けたリファクタリングで
  `test_app.py` と `test_fly_in.py` から移した

- `tests/pathfinding/conftest.py` — `grid_network`(20×20 の格子。`make_network` で組む)
- `tests/pathfinding/test_flow_map.py` — `pathfinder.py` のフローマップ:
  `last_turn` と `Route.arrival_turn`(LT01〜LT07: ドローン0は経路なしでも0・経路なしで機がいれば `ValueError`、
  rate 1・2 の1本、長さの違う2本の和、T より長い経路は数えない、出発ターンに1ゾーン目に入る数え方)、
  フローと経路の分け方(FM01〜FM16: 一本道、分岐を1機では1本・2機以上で2本、細い合流・広い合流、
  接続容量・ゾーン容量で決まる rate、restricted の2ターン、T が下がらない経路は足さない・残さない、
  priority は同じ長さの中のタイブレークだけで priority の数が多い方、押し戻し(back arc)での組み替え、
  start / end は無制限・restricted な end、`max_drones` の無いハブ。`FlowGraph` を直接使う補助のケース
  (経路なし、弧のコストと `push` 後の経路、priority の弧のコスト))、
  押さえた地図(HM01〜HM08: 使うゾーン・接続だけ、blocked は入らない、容量は1ターンに流す数、共有するゾーン・接続は合計、
  宣言順と接続名を保つ、`max_drones` 以外の属性を保つ、元の地図を変えない、ドローン0は start と end だけ)、
  `Pathfinder` の構築と E2E(PF01〜PF05: 構築時の到達不能検出(4パターン)、孤立ゾーン、パーサー経由
  (到達不能マップはパース成功・経路探索で失敗)、課題の例と配布マップ10枚の1機の最短、20×20 の格子が1秒以内)。
  `FlowMap` は `Network` に `__eq__` が無いので `==` で比べず、`routes` / `last_turn` / 押さえた地図の中身を別々に比べる

- `tests/simulation/conftest.py` — スタブのスケジューラ(台本どおりの `ScriptedScheduler`、1機のフローマップの最速の経路を
  貪欲にたどる `FollowerScheduler`、何もしない `IdleScheduler`、往復し続ける `OscillatingScheduler`。どれも `decide_moves` だけの
  ふつうのクラスで、`MoveDecider` を満たし、エンジンに直接渡す)、
  render の呼び出しを記録する `recorder`、`begin` / `render` / `close` を呼ばれた順に1つのリストに記録し、指定した
  メソッドで失敗もできる `call_log`(Stage 7)、1ターンを出力の文字列にする `fmt`、
  本物の `Scheduler` を作る `real_scheduler`、本物の `Pathfinder` の `flow_map` を `monkeypatch` で差し替えて、テストが
  渡したフローマップで本物の `Scheduler` を作る `fixed_scheduler`(壊れたフローマップの検査用)
- `tests/simulation/test_state.py` — `SimulationState`: 構築(全機が start に `AT_ZONE`)、`enter_zone` の数え方、
  end への到着で配達済み(占有に残らない)、`enter_transit` の予約と接続の使用、`complete_transit` で予約が占有に置き換わること、restricted な end への到着、基本操作の前提違反。
  `Move`(MV01〜MV03): `text` と接続名の既定値 `None`、resolver が付ける接続名(出発は使った接続・restricted への
  出発は行き先も接続名・着陸は `None`)、frozen で接続名も等価性に入ること。
  `Drone.history`(DH02〜DH07): 構築時は機ごとに別の `["s"]`、入ったゾーンを足す(動いた機だけ)、restricted は飛行中には
  足さず着陸で足す、end も足す、restricted な end への着陸、resolver が拒否したターンでは履歴も変わらないこと
- `tests/simulation/test_turn_resolver.py` — `TurnResolver`: 出力のドローンID順(自動の到着と指示が混ざっても)、
  ゾーン容量(上限ちょうどは合法・同じターンに出ていく分は使える・3機の循環)、start/end は無制限、接続容量
  (両方向で共有・入れ替わり)、restricted の2ターン移動(出発時は宣言どおりの接続名、次ターンに自動到着・
  着陸は接続を空けるので容量1でも同じターンに出発できる・飛行中への指示は拒否・restricted な end)、
  予約表の規則(T25〜T30): 着陸は最終負荷に数え、同じターンに出ていく機(restricted へ出発する機も)の空きを使えること、
  restricted への出発は出発のターンにはそのゾーンに数えないこと、着陸できない機は「接続上で詰まった」
  (`turn N: D<id> is stuck on connection '<接続>': zone '<ゾーン>' is full` の完全一致。2機なら小さい ID、
  容量ちょうどは合法で1つ超えると詰まり)、着陸のないゾーンの違反は従来のメッセージ、詰まりの後も続けられること、
  不正な指示(存在しないドローン/ゾーン・隣接していない・blocked・2つの指示・今いるゾーン)、配達済みへの指示と出力、
  違反後に状態が一切変わらないこと(到着も適用されない。接続上の詰まり・ゾーン容量の違反を含む)とその後も続けられること、
  自己ループでの移動の拒否(normal / restricted)、戻り値が `Move` であること(出発は接続名を持つ)
- `tests/simulation/test_engine.py` — `SimulationEngine`: 正常終了(空のターンなし・ID順)、render はターンの適用後に
  1回ずつ(observer は省略可)、誰も動かないターンの `SimulationError`、到着だけのターンは進行とみなすこと、
  ターン数の上限(振動・ちょうど上限で終わる境界)、既定の上限 `default_turn_limit`、resolver の例外が伝わり違反した
  ターンでは render しないこと、構築直後の状態、パーサー経由の E2E(課題のサンプルマップの出力7行、corridorA を
  blocked にして restricted の roof1 を通る出力12行。これは貪欲なスタブ `FollowerScheduler` の結果)、
  「接続上で詰まった」がエンジンからそのまま伝わり、詰まったターンでは render しないこと(G12)
- `tests/simulation/scheduling/test_scheduler.py` — `scheduler.py`: `plan_departures`(PD01〜PD09: 1ターンに rate 席、
  出発ターンは `1 .. T − turns + 1`、到着の早い順 → 出発の早い順 → 経路の番号順(名前ではなく `routes` の並び)、
  T までに着けない経路には席がない、ドローン0、席が足りないときの `SimulationError`、課題の例の出発(D2・D4 が roof1)、
  `Departure` の値と frozen)。
  `Scheduler`(SC01〜SC20): フローマップは最初の判断で作ること、指示の並びは end に近いゾーンから(ID 順ではない。
  課題の例の指示を順序ごと)、start で出発のターンを待つこと、飛行中・配達済みには指示しないこと、restricted への指示は
  ゾーン名、同じターンに2回呼んでも状態と履歴を変えず同じ指示、ターン0では呼ぶたびに計画し直しそれ以降は作らないこと、
  エラー(出発のターンを過ぎた・経路のない機・経路から外れた・経路の最後まで来たのに配達されていない・いたゾーンに戻る・
  押さえた地図に接続がない・押さえた接続/ゾーンが満杯・計画の席が足りない。どれもメッセージの完全一致。壊れたフローマップは
  `fixed_scheduler` で渡す)、課題の例と restricted だけの例が resolver に受理されて `flow_map.last_turn` ターンで終わること
- `tests/simulation/scheduling/test_scheduler_maps.py` — 本物の `Scheduler` の E2E: 課題のサンプルマップで本物のスケジューラの出力5行
  (`scheduler_output`)と完全一致、
  restricted だけの経路の出力8行(1本の経路に毎ターン1機)、
  毎ターンの不変条件(`run_checked`: 最初の判断の後に公開の `plan_departures` で出発を作り直し、1機1指示・指示は `AT_ZONE` の機だけ・
  行き先はその機の経路の次のゾーンで `history` に無い・start 以外の機は待たず、start の機は出発ターンだけ指示を受ける・
  resolver が受理・誰かが動く・既定の上限内。終わったとき各機の `history` は経路と等しく、配達のターンは
  `route.arrival_turn(出発ターン)`、全体のターン数は `flow_map.last_turn`)を課題の例と配布マップ10枚で確認、
  配布マップのターン数(VII.6 の最適値以内、challenger は最適値43ちょうど)、アーカイブの中身、決定的であること、
  1機の最速の経路(`flow_map(1).last_turn`)を下回らないこと。
  小さな網の出力(R09〜R15。出力の行を完全一致で比べ、`run_checked` でも同じ行で完走すること):
  restricted 1つ(4行)、出口の細い restricted(K1 6行・K2 7行)、restricted の2本(5行)、restricted が続く網
  (6行・9行・間に normal で8行)、restricted 2つを通る1本の経路の網(11行)、restricted の連なり(8行)、restricted の多いランダムなマップ300枚
  (`random.Random(2026)`。詰まり・容量違反なしで完走し、2本以上の経路を使うマップが少なくとも1枚あること。失敗時はマップの記述をメッセージに出す)。
  実際のマップ(R16〜R20): 課題の例のターンごとの指示(順序ごと。SC03 と同じ値)、priority_puzzle の出力6行(4ターンと5ターンの2本)、
  `s-a a-g s-r r-g` を2・3・4機で(2機では r を使わない)、配布マップ10枚のターン数の固定値(すべて最適値。変わったときは、
  この表とベンチマークの記録を一緒に更新する)、各マップで使う経路の数(課題の例2・easy 1/2/1・medium 1/1/2・hard 1/1/1・
  challenger 1。`flow_map.routes` の数と実際に使われた経路の数の両方)。
  配布マップはリポジトリ直下の `maps.tar.gz`(git 管理)を共有の `provided_map` が `tarfile` でメモリ上で、先頭のコメントも含めてそのまま
  読む(パーサがコメントを読み飛ばすことも確かめる。アーカイブが無ければ分かりやすいメッセージで失敗する。skip にはしない)

- `tests/simulation/test_engine_hooks.py` — `SimulationEngine.run` が観測者(`TurnObserver`)を呼ぶ契約(Stage 7): `begin` は1ターン目の前に
  1回(ターン0・全機が start)、`render` は毎ターンそのターンの `moves` で、`close` は最後に1回。`SimulationError`
  (誰も動かない・ターン数の上限・不正な指示)、`begin` の失敗、`render` の失敗のどれでも `close` を呼び、例外はそのまま伝わること。
  `run(observer=...)` のキーワード(EO01)、観測者なしの `run()` とコンストラクタのキーワード `world` / `decider` /
  `max_turns`・既定の上限(EO02)
- `tests/simulation/test_observer.py` — `ObserverGroup`(OG01〜OG07。OG01〜OG05 は旧 `test_composite.py` の VC01〜VC05):
  呼び出しを観測者の順に配る(同じ `state` / `moves`)、1つの close が失敗しても残りを閉じる、複数の失敗は最後を送出し
  前の失敗を `__context__` でつなぐ、観測者なし、render の失敗はそのまま伝わる、受け取った列の複製(タプルからも
  `list`)、エンジンからは1つの観測者に見え各観測者に順に届くこと

- `tests/visualization/conftest.py` — `coord_network`(座標と色つきでゾーンを登録する。最初が start、最後が end)。
  matplotlib を Agg バックエンド(ディスプレイ不要)に切り替える
- `tests/visualization/matplotlib_window/test_geometry.py` — matplotlib のウィンドウの配置(GM01〜GM06): ゾーンの半径(最も近い2点の距離の0.3、
  1を超える距離は1とみなす)、同じ座標のゾーンを離すこと、ゾーンの横を通る線はまっすぐ・ゾーンの上を通る線はそれをよける弧
  (上側から試す)、自己ループはゾーンの上の小さな輪、直線の中点
- `tests/visualization/matplotlib_window/conftest.py` — `network`(`s - r - g` の一列。scene と view のテストで共有)
- `tests/visualization/matplotlib_window/test_matplotlib_window_scene.py` — matplotlib の描画 `MapScene`(VG01〜VG06・VG10): ゾーンが地図の単位で配置の半径の
  パッチとして縦横同じ縮尺で描かれること、restricted は四角、ゾーンに重なる接続だけが曲がること、タイトルのターン数と
  同じ地点のドローンの数、飛行中のドローンは接続の中点・その接続だけ水色で2倍の太さ(着陸後は元に戻る)、色名の解決(matplotlib の色名 → 灰色)
- `tests/visualization/matplotlib_window/test_matplotlib_window_view.py` — matplotlib のウィンドウ `MatplotlibWindowVisualizer`(VG07〜VG09): ディスプレイなしでは
  `VisualizationError`(図を残さない)、`--matplotlib-window` の `main` は終了コード1と1行のエラー、ウィンドウを閉じた後は描かないこと
- `tests/visualization/terminal/test_terminal_colors.py` — 端末表示の色名の表 `rgb`: 表の値(似た赤を区別)・全エントリが 0〜255 の3つ組、大文字小文字を
  区別しないこと、配布マップ(`maps.tar.gz`)の色名17種のうち `rainbow` 以外がすべて表にあること、知らない名前・空・`None` は
  `None`
- `tests/visualization/terminal/test_terminal_view.py` — `TerminalVisualizer`: 既定の出力先が stderr(stdout は空)、begin の見出し・
  凡例・ゾーンの表・`drones:`、`frame` は書かずに行を返し render がそれを書くこと、restricted(接続名・予約 `+1`・飛行中)・
  blocked(`--`)・end(配達数)の表示、ドローンIDの範囲表記、幅での折り返しと長い名前の省略、色の強制 on/off・自動判定
  (端末かどうか・`NO_COLOR` は空でない値のときだけ)、知らない色・色なしは塗らない、close は flush するだけ、
  状態を変えないこと、課題のサンプルマップの E2E

対象はStage 1(Domain Model)・Stage 2(Parser & Validation)・Stage 3(Pathfinding)・Stage 4(Simulation Engine)・
Stage 5(Multi-Drone Scheduler)・Stage 6(Output Formatter)・Stage 7(Visualization。最小構成版ではターミナル表示と、`--matplotlib-window` の最小限の matplotlib 表示)と、CLI / Application / エントリポイント
(`app.py`・`turn_log_printer.py`・`fly_in.py`)。
`Makefile` は単体テストの対象外(手動で確認する。`docs/research/2026-10-18_test-design-cli-app.md`、develop ブランチ)。
以降の実装が進み次第、対応するテストを追加していく想定。
