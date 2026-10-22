# テスト設計: 拡大縮小・移動となめらかな描画(ビジュアライズの改善 3回目)

- 日付: 2026-10-22
- フェーズ: **テスト設計**(作成は `test/visual_zoom`)
- 対象: `droneflow/visualization/camera.py`(`Camera`・`visible`)、`graphical_view.py` の `_Window`(`_view_event`・`_detail`・`_track_mouse`)、
  `_Layout.zone_at(point, reach)`
- 参照した決定: `docs/decisions.md` 2026-10-22「グラフィカル表示に拡大縮小・移動と、なめらかな描画を入れる」1〜5
- 方針: `Camera` は pygame なしで `tests/visualization/test_camera.py`。窓の操作は既存の `test_graphical_view.py`(ヘッドレス)に足し、
  イベントは `pygame.event.Event` を作って `_view_event` に直接渡す(待ちのループを回さない)。ID は **CA**(Camera)・**VZ**(表示)。

## A. Camera(`tests/visualization/test_camera.py`)

| ID | 何を確かめるか | 入力 | 期待 |
|---|---|---|---|
| CA01 | 最初は全体表示 | `Camera(8)` | `zoom == 1`、`offset == (0, 0)`、`to_screen((10, 20)) == (10, 20)` |
| CA02 | 画面 ↔ 地図の往復 | zoom 2・offset (5, -3) | `to_screen((10, 20)) == (25, 37)`、`to_map((25, 37)) == (10, 20)` |
| CA03 | カーソルの下の点は動かない | `zoom_at((300, 200), 1.25)` を3回 | `to_screen(to_map((300, 200)))` が毎回 (300, 200)(±1)、zoom は 1.25³ |
| CA04 | 倍率の上下限 | max 8 で 1.25 倍を 20 回 / 0.8 倍を 20 回 | 8 / 0.5(`MIN_ZOOM`) |
| CA05 | max は1より小さくならない | `Camera(0.3)` で 2 倍 | zoom 1 のまま |
| CA06 | 移動 | `pan(10, -4)` | `to_screen((0, 0)) == (10, -4)` |
| CA07 | 全体表示に戻す | 拡大・移動の後に `fit()` | zoom 1、offset (0, 0) |
| CA08 | 画面の中か | size (100, 50)、margin 5 | (0,0)・(105, 55) は中、(106, 0)・(0, -6) は外 |

## B. 表示(`tests/visualization/test_graphical_view.py` に追加)

| ID | 何を確かめるか | 入力 | 期待 |
|---|---|---|---|
| VZ01 | ホイールで拡大・縮小 | `MOUSEWHEEL(y=1)` / `(y=-1)` を `_view_event` | True を返し、zoom が 1.25 / 1.0 に戻る |
| VZ02 | ドラッグで移動 | 左ボタンを (100,100) で押し、(130, 90) へ動かし、離す | offset が (30, -10)。離した後の動きでは移動しない |
| VZ03 | `f` で全体表示 | 拡大・移動の後に `KEYDOWN(K_f)` | zoom 1、offset (0, 0) |
| VZ04 | ほかのキーは扱わない | `KEYDOWN(K_SPACE)` | `_view_event` が False(今までの処理に回る) |
| VZ05 | 縮小すると名前を省き、点にする | 課題の例の倍率1の `_detail()`、間隔の狭いメッシュ(20×20)の倍率1と 0.5 | 課題の例: 半径はそのまま・名前あり。メッシュの倍率1: 半径はそのまま・名前なし(間隔 < 40)。メッシュの 0.5 倍: 半径が元より小さい。作成時に訂正: 課題の例の 0.5 倍は、最も近いゾーンの間隔によっては点になるので使わない |
| VZ06 | 拡大しても、マウスの下のゾーンが分かる | 課題の例を 2 倍に拡大し、roof1 の画面位置へ `MOUSEMOTION` | `_hover` の名前が roof1 |
| VZ07 | 拡大すると名前の幅も広がる | `_Layout.spacing` が小さいマップで、倍率1と4の名前 | 倍率1では `~` で切れ、4では切れない(`zone_title` に渡す幅が倍率で変わる) |
| VZ08 | 画面の外は描かない | 課題の例を大きくずらす(`pan(5000, 0)`)して `redraw` | 例外なく描け、`pygame.draw.aacircle` の呼び出しが0回(ゾーンもドローンも画面外) |
