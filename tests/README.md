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

## 現在のカバレッジ範囲

- `tests/models/test_zone.py` — `ZoneType.turn_cost` / `is_traversable`、
  `Zone.has_unlimited_capacity`
- `tests/models/test_connection.py` — `Connection.involves` / `other_end`
- `tests/models/test_drone.py` — `Drone.is_delivered`
- `tests/models/test_network.py` — `Network` の登録・検索・隣接・start/end取得と、
  それぞれの例外契約(`ZoneNotFoundError` / `SimulationError`)
- `tests/test_errors.py` — `ZoneNotFoundError` の例外階層・属性、`UnreachableGoalError` の例外階層
  (`FlyInError` の子で `ParseError` / `SimulationError` とは別)・属性・行番号なしのメッセージ
- `tests/parsing/test_map_parser.py` — `MapParser`(章VII.4のパーサ制約全般):
  仕様書記載のサンプルマップの正常系パース、メタデータ省略時のデフォルト値
  (zone/color/max_drones/max_link_capacity)、start/end hubのmax_drones正規化、
  重複(ゾーン名・接続・start/end hub)の即時検出、start/end hub欠落、不正な
  ゾーンタイプ・メタデータキー・メタデータ構文・座標・ゾーン名、未定義ゾーンへの
  接続参照、空ファイル、自己ループ接続・座標重複の許容(いずれもParseErrorにしない)
- `tests/parsing/test_map_format.py` — 仕様表(`MapFormat`)の変換部品(整数・正の整数・
  ゾーン名・ゾーンタイプ・接続の両端)、`FieldSpec` の既定値とエラー文言、hub / start_hub /
  connection / header の組み立て(max_drones の既定値と start/end での破棄)
- `tests/parsing/test_line_tokenizer.py` — `LineTokenizer` の構文検査(トークン数・括弧・
  key=value・未知キー・未知キーワード)と行番号、ヘッダー行の別扱い
- `tests/parsing/test_map_rules.py` — 行をまたぐ規則(ゾーン名重複・start/end重複・
  未定義ゾーンへの接続・接続重複と自己ループ)
- `tests/output/test_formatter.py` — `TurnLogFormatter`: `D<ID>-<行き先>` の空白区切り整形、
  呼び出し順の保持(ソートしない)、接続名のそのまま出力、空ターンのスキップ、`capsys` での標準出力検査

- `tests/pathfinding/conftest.py` — 共有フィクスチャ: `make_network`(`"s-a a-g"` のような記述から
  `Network` をコード内で組む。記述順=接続の宣言順)、`grid_network`(20×20 の格子)、`write_map`(`tmp_path` にマップを書く)
- `tests/pathfinding/test_distance_map.py` — `DistanceMap`: ゾーンタイプ別の進入コスト(restricted=2・priority=1、
  restricted な end を含む)、blocked の除外と通過不可、行き止まり・孤立ゾーン、自己ループ・閉路、
  存在しない名前の `ZoneNotFoundError`、end が blocked のときの防御的な挙動、20×20 格子での距離
- `tests/pathfinding/test_pathfinder.py` — `Pathfinder`: 構築時の到達不能検出(`UnreachableGoalError`、4パターン)、
  `distance` の委譲、`next_hops` の判定(`turn_cost + 距離` で比較)・並び順(priority は次の1手の同点の中だけで先頭、
  それ以外は接続の宣言順、安定ソート)・遠回りの priority を選ばないこと・blocked の除外・空リストを返す場所、
  `best_route` の `total_cost` と `from_zone` 指定・例外の種類、経路の整合性チェック、
  パーサー経由の E2E(課題のサンプルマップ、到達不能マップはパース成功・経路探索で失敗)

対象はStage 1(Domain Model)・Stage 2(Parser & Validation)・Stage 3(Pathfinding)・Stage 6(Output Formatter)。
Stage 4以降(シミュレーション等)の実装が進み次第、対応するテストディレクトリを追加していく想定。
