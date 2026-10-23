# テスト設計: 本家 pygame しか無いときのエラー

- 日付: 2026-10-23
- フェーズ: テスト設計(作成は `fix/require_pygame_ce`)
- 対象: `droneflow/visualization/graphical_view.py`(`pygame.IS_CE` の確認)、`droneflow/app.py` `Application._graphical_view`
- 参照した決定: `docs/decisions.md` 2026-10-23「本家 pygame しか無いときも『pygame-ce が要る』のエラーにする」

| ID | 内容 |
|---|---|
| AA16 | `sys.modules` の `pygame` を `IS_CE` の無い代わりのモジュールにすると、graphical / both で `VisualizationError`(pygame が無いときと同じ文言)、原因は `name == "pygame"` の `ModuleNotFoundError`、stdout・stderr は空 |
| AA10 / `break_palette_import`(test_fly_in.py)の手直し | 代わりの pygame モジュールに `IS_CE = True` を付ける(付けないと palette より先に pygame-ce の確認で止まり、確かめたいことが変わる) |
