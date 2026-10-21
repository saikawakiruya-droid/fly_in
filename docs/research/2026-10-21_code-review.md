# コード全体の独立レビュー(10観点)とリファクタリング計画

- 日付: 2026-10-20〜21
- 対象: develop(ff45586 時点)。読むだけのレビューを、観点ごとに独立したエージェントで並行して行った(観点9「計算量と性能」は対象外とした)。
- 観点: 1 スケジューラ周りの整合 / 2 課題要件 / 3 エラー処理と境界 / 4 合成優先・OOP / 5 層と依存 / 6 未使用・重複 /
  7 docstring と文書の一致 / 8 命名と型 / 10 main への準備 / 11 評価で説明できるか
- 指摘の ID は「R<観点>-<番号>」。各レビューの全文は会話ログ(2026-10-21)の要約と、このファイルの表にまとめた。

## 全体の結論

- **不正なターン・詰まり・非決定性はない**(R1: ランダムなマップ約5,500枚、R2: 自作の独立チェッカーで全マップ違反0件)。flake8・mypy(課題のフラグ、--strict、--python-version 3.10)・pytest 767件はすべて通る。
- README の実行例・エラー例・統計は実際の出力と一致(R7、R11)。
- 最も重い発見は次の3つ。
  1. **性能の退行**(R7-2、R3-8): 遠回りの導入後、待つ機ごとに全機の位置を数え直すため、1ターン O(D²)、全体 O(D³)。3,000機で 33秒 → 318秒。
     観点9は対象外にしたが、遠回りの実装が持ち込んだ退行なので直す対象に含める(ターンログは変わらない見込み)。
  2. **案B の後で古くなった説明**(R7-1、R1-3): 「同じゾーンのドローンは選べる手が同じ」がコード・README・decisions に残る。実際は機ごとの「いたゾーン」と予約で違う。
  3. **前回「通らない」と読んだ分岐が通る**(R1-1): 「このターンに立ち退きが決まった未判断の機は待つ」が遠回りで到達可能になった。テストが無い。
- 提出(main)に向けては、履歴のセッションURL(push 済み)・作者情報・tests 前提の README/Makefile/requirements など、判断の要る項目がまとまって残る(R10)。

## 指摘の一覧(要約)

### 挙動が変わらない整理(判断不要として実施する候補)

| 区分 | 内容 | 主な ID |
|---|---|---|
| 性能 | ゾーンごとの機数を1ターンに1回(または移動ごとに差分で)数え、`DetourPolicy` の数え方を引くだけにする。`budget` は候補があるときだけ計算する | R7-2, R3-8 |
| 文書 | 「同じゾーンは選べる手が同じ」の訂正、`decide_moves` の到達不能の補足、`MapParser.parse` の Raises、`Move`/`MoveOrder` の担当、`CompositeVisualizer` の用途、`render` の Raises、`default_turn_limit` の根拠、立ち退きの再帰が終わる理由、`_try_hop` の `extra` の意味 | R7-1, R7-8〜12, R1-3, R1-4, R11-9, R11-3 |
| 文書 | docstring の無い公開クラス・メソッド・`__init__` に1行の docstring | R2-6, R7-7 |
| README | メモリの項の食い違い、計算量と計測のやり直し、`make install` の説明、「規則6'」の番号をやめ内容で呼ぶ、priority をタイブレークにする理由、ahead の見積もりの前提と「下流すべて」、継承を使う所の説明、`+N` の凡例 | R7-2, R7-3, R7-5, R11-4〜6, R11-10, R11-11 |
| 決定記録 | 古くなった「未決」への追記(課題の例7ターン、判断順の並べ方、距離が真に減る遠回り)、詰まる場所の発見の API と未使用の扱い | R7-4 |
| 型の置き場所 | `Position` を `state.py` の NamedTuple(`zone`, `since_turn`)へ | R5-3, R8-4 |
| 層 | エンジンが受け取る観測者の型(Protocol)を simulation 側に置き、`CompositeVisualizer` も移す。`visualization.base.Visualizer` はそれを使う(パッケージ単位の循環をなくす) | R5-1, R5-2 |
| OOP | `SimulationEngine` は `decide_moves` だけの Protocol を受け取る。`Application` にスケジューラの作り方を渡せるようにする(テストの継承と monkeypatch をなくす) | R4-1 |
| 重複 | `Zone.capacity`(無制限の判定を1か所に)、到着ターンの計算、`ReservationTable.leaves_after`、接続名からの逆引き、`_try_hop` で `has_room` を使う、`Pathfinder` の隣接走査の共通化、遠回りの総コストの二重計算、`UniqueConnection` は `connection_between` を使う、グラフィカル表示のターンログの書式は `TurnLogFormatter` を使う | R4-2, R4-3, R4-11, R6-6, R6-10〜14, R6-16, R8-13 |
| 値オブジェクト | `Zone`/`Connection`/`World`/`Route`/`Move` を frozen に(`zone_flow` の `id()` の回避策が要らなくなる)、`Network` の公開の可変 dict/list を読み取り専用に | R8-3, R4-6, R8-10 |
| 命名 | `Scheduler._detours` → `_detour_policy`、`Pathfinder._distances` → `_distance_map`、`holding` の二重の意味、`_first_hop` → `_take_first_hop`、`has_seat`/`has_seats` の見分けにくさ、ターン番号の語彙、`zone` が str と Zone で混在 | R8-5〜9 |
| 分割 | `Scheduler`(約325行)を「判断順」「一手の試行」「計画のやり直し」に分ける。1ターン分の位置を `PositionBoard` に。グラフィカル表示(602行)とターミナル表示の責務の分割 | R4-4, R4-8, R4-9, R4-10 |
| 型の精度 | `map_format` の `Any`(Generic の FieldSpec と TypedDict)、`--visual` を Literal に、`SimulationState` の読み取り専用のビュー(Protocol) | R8-1, R8-2, R4-5, R4-7 |
| テスト | R1-1 の分岐を通るテストを足す | R1-1 |

### 判断が要るもの

| # | 内容 | ID |
|---|---|---|
| 1 | 分析用の最小カットのコード(3ファイル313行、テスト50件)を残す / 消す / 別パッケージ・提出物の外へ | R6-1, R5-4, R11-7 |
| 2 | 実行に使われないもの(`best_route`/`Route`、`emit`、`WAITING`、`free_capacity`、`turns_remaining`、`TurnLogPrinter(formatter=)`)を消すか | R6-2〜9, R11-7 |
| 3 | このターンに立ち退きが決まった未判断の機も判断に回す(まれなマップで短くなる。悪化0) | R1-2 |
| 4 | パーサーを厳しくする: ASCII の数字だけ(`+2`・`1_0`・Unicode の数字を拒否)、ゾーン名の制御文字、座標の範囲、BOM を読み飛ばす、長いメッセージを切る、ファイル全体の誤り(空ファイルの `line 0`、start/end の欠落)は行番号を出さない、行末の `#` コメント | R2-3, R2-4, R3-1, R3-2, R3-4〜7 |
| 5 | 出力の安全策: Windows で stdout をリダイレクトしたときの文字コード、stderr が閉じたときの終了コード、グラフィカル表示の長い名前 | R2-5, R3-3, R3-9, R3-10 |
| 6 | 配布マップは1行目がコメントなので全滅する読み方(2026-10-16/18 の決定)を見直すか | R2-1 |
| 7 | `map_rules.py` の ABC の継承を委譲に変える(2026-10-04 の決定を変える) | R4-12 |
| 8 | ライブコーディング(`--capacity-info` など)の準備として `Move` に使った接続を持たせる | R11-1 |
| 9 | 同じターンの計画し直しの仕組み(テストでだけ使う)を残すか | R11-8 |
| 10 | main への反映(方式、`make test`、README の Testing、requirements、setup.cfg、`.gitignore`、`maps.tar.gz`、CLAUDE.md の一覧) | R10-1〜10, R2-8 |
| 11 | 履歴のセッションURL(main 3コミット・develop 初期4コミット、push 済み)と作者情報(noreply でない)。直すには履歴の書き換えと強制 push が要る | R10 |

### 変更不要と判断されたもの

例外の階層(is-a)、`CompositeVisualizer`・`_GuardedView`・`TurnLogPrinter` の委譲、pygame の遅延 import、`except Exception` の2か所(最後の砦と close)、
`__init__` の re-export なし、モジュール単位の循環なし、Python 3.10 の構文、`cast`/`type: ignore`/`assert` なし。
