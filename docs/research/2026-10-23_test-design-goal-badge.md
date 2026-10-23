# テスト設計: goal の配達済みドローンのバッジ

- 日付: 2026-10-23
- フェーズ: テスト設計(作成は `feature/goal_drone_badge`)
- 対象: `droneflow/visualization/graphical_view.py`(`_Window.drone_point`、`_Window._draw_drones`)
- 参照した決定: `docs/decisions.md` 2026-10-23「グラフィカル表示で、goal に配達済みのドローンを数のバッジで描く」

| ID | 内容 |
|---|---|
| VO08 | 配達済みのドローンの `drone_point` は goal の位置(`layout.position("g")`。これまでは None) |
| VO09 | `s-a a-g` で goal に配達済みが1機なら札なし(点)、5機なら札が1つ(VO07 と同じく角丸の四角の数で数える) |
| 既存 | 軌跡のテスト(着陸・配達の軌跡)は `_point_after` を消しても同じ結果になることを確認する |
