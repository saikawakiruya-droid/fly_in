# 2026-10-23 グラフィカル表示の aacircle エラー

開始: 2026-10-23

## 依頼: `python3 fly_in.py --delay 5 --visual both ./maps/subject_example.txt` が `pygame.draw` に `aacircle` が無いと落ちた

- `aacircle` は pygame-ce だけの関数(decisions.md 2026-10-22「拡大縮小・なめらかな描画」で導入)。システムの `python3` に本家 pygame
  (または古い pygame-ce)が入っていて、`.venv` を使わずに実行したためと推定。本家 pygame でも import は通るので、
  「pygame が無い」の案内にならず内部エラーになる。
- 確認方法と回避策(`.venv/bin/python` か `make run` で実行)を伝えた。コード側の改善案(`pygame.IS_CE` の確認)は提案のみで未決。
- bugs.md に記録(未対応・原因は推定)。

## 依頼2: 直しておいて(範囲は「エラーの案内を直す」を選択)

- `make run` で動いたので原因は推定どおり。`fix/require_pygame_ce` で修正(decisions.md 2026-10-23、テスト設計
  `docs/research/2026-10-23_test-design-require-pygame-ce.md`、AA16、README 両版)。pytest 897 件通過、flake8 通過。
  mypy は Windows のアプリ制御ポリシーで DLL が読めず、この環境では実行できなかった。develop へのマージは未(許可待ち)。

## 依頼3(質問): 終了後に pygame の窓があるとプログラムが終わらない / goal にドローンが表示されない

- 終了後に待つのは設計どおり(decisions.md 2026-10-17 の4、`hold_final=True`)。Esc・q・× で閉じると終わる。自動で閉じる案は未決。
- goal のドローン: 配達済みは `active_drones()` から外れ、`drone_point` も None を返すので点を描かない。goal の下の `N in` と
  上部の `delivered N/M` で数だけを表示している。goal に数のバッジを描く案は未決。

## 作成・変更したファイル

- `docs/bugs.md`(追記・対応済みに更新)
- `docs/decisions.md`(追記)、`docs/research/2026-10-23_test-design-require-pygame-ce.md`
- `droneflow/visualization/graphical_view.py`、`tests/test_app.py`、`tests/test_fly_in.py`、`tests/README.md`、`README.md`、`README.ja.md`
- `docs/conversation_log/2026-10-23/02_pygame_aacircle_error.md`(このファイル)
