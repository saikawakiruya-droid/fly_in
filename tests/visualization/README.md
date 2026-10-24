# tests/visualization/

`droneflow/visualization/`(Stage 7)の単体テスト。ソースと同じく、ターミナル表示は `terminal/`、グラフィカル表示は `graphical/` に分け、
両方で使う色名の表(`test_palette.py`)と `conftest.py` はこの直下に置く。エンジンが可視化を呼ぶ契約(`begin` / `render` / `close`)のテストは
`engine.py` のテストなので `tests/simulation/test_engine_hooks.py` にある。
`ObserverGroup` のテストは `tests/simulation/test_observer.py`(旧 `test_composite.py` の VC01〜VC05 を移した)。

## ファイル

- `conftest.py` — `coord_network`(座標・色つきのネットワーク)。matplotlib を Agg バックエンドに切り替える。`tty_stream`(`isatty()` が True の `StringIO`)は
  CLI のフェーズで `tests/conftest.py` に移した(Application のテストと共有)
- `test_palette.py` — 色名の表(VP01〜VP04)
- `terminal/test_terminal_view.py` — `TerminalVisualizer`(VT01〜VT11・VT15・VT16)
- `graphical/test_geometry.py` — グラフィカル表示の配置: ゾーンの半径・重なったゾーンの分散・接続の直線と弧(GM01〜GM06)
- `graphical/test_graphical_view.py` — matplotlib の表示 `MapScene` / `GraphicalVisualizer`(VG01〜VG10)

## 書き方の約束

- ターミナル表示は `StringIO` に書かせて文字列で比べる。`color=False` と `width` を明示し、端末の幅や環境変数に左右されない
  ようにする(色を見るテストだけ `color=True`)。「端末」は `tty_stream` で作り、本物の端末・`sys.stdin` は使わない。
- matplotlib の表示は Agg バックエンド(ディスプレイ不要)で、ウィンドウを開かずに `Figure` に描かせて図の中身を調べる。
  ウィンドウが要るテストは、開けないこと(`VisualizationError`)を確かめるか、Agg のキャンバスを対話的なものとして通す。
- 設計: `docs/research/2026-10-18_test-design-stage7-visualization.md`(develop ブランチ)

## 実行

```sh
python -m pytest tests/visualization/
```
