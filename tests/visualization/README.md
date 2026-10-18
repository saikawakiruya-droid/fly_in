# tests/visualization/

`droneflow/visualization/`(Stage 7)の単体テスト。エンジンが可視化を呼ぶ契約(`begin` / `render` / `close`)のテストは
`engine.py` のテストなので `tests/simulation/test_engine_hooks.py` にある。

## ファイル

- `conftest.py` — `coord_network`(座標・色つきのネットワーク)。pygame 不要。`tty_stream`(`isatty()` が True の `StringIO`)は
  CLI のフェーズで `tests/conftest.py` に移した(Application のテストと共有)
- `test_palette.py` — 色名の表(VP01〜VP04)。pygame 不要
- `test_composite.py` — `CompositeVisualizer`(VC01〜VC05)。pygame 不要
- `test_terminal_view.py` — `TerminalVisualizer`(VT01〜VT16)。pygame 不要
- `test_graphical_view.py` — `GraphicalVisualizer`(VG01〜VG18)。pygame が無ければファイルごと skip

## 書き方の約束

- ターミナル表示は `StringIO` に書かせて文字列で比べる。`color=False` と `width` を明示し、端末の幅や環境変数に左右されない
  ようにする(色を見るテストだけ `color=True`)。「端末」は `tty_stream` で作り、本物の端末・`sys.stdin` は使わない。
- グラフィカル表示はファイル内の `headless` フィクスチャで動かす: `SDL_VIDEODRIVER=dummy` にして `pygame.display.init()` し、
  キューを空にして、番犬のタイマー(既定3秒後に `QUIT`)を仕掛ける。teardown で番犬を止め、ディスプレイを閉じる。
- ビューは `begin` / `render` / `close` の中で入力を待つので、キー・マウス・`QUIT` のイベントは**呼び出しの前に**積む。
- 実時間の `sleep` と経過時間のアサーションは使わない。自動再生は `delay=0`、ステップ実行は `delay=60`(イベントが来ない限り
  進まない)にし、「待った / 待たなかった」は窓の状態(`is_open`)で確かめる。待ち続けた場合は番犬で窓が閉じ、アサーションで落ちる。
- 内部名 `_Layout`(座標変換)と `_Window.wait_for_quit`(`monkeypatch` のスパイ)に依存するテストがある(VG03・VG04・VG15・VG14)。
- 設計: `docs/research/2026-10-18_test-design-stage7-visualization.md`(develop ブランチ)

## 実行

```sh
python -m pytest tests/visualization/
```
