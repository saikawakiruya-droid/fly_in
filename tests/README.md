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
- `tests/test_errors.py` — `ZoneNotFoundError` の例外階層・属性
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

対象はStage 1(Domain Model)・Stage 2(Parser & Validation)。Stage 3以降
(経路探索、シミュレーション等)の実装が進み次第、対応するテストディレクトリを追加していく想定。
