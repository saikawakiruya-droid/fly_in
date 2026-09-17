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

対象はStage 1(Domain Model)。Stage 2以降(パーサ、経路探索、シミュレーション等)の
実装が進み次第、対応するテストディレクトリ(`tests/parsing/` 等)を追加していく想定。
