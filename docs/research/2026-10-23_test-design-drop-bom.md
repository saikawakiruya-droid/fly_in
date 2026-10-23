# テスト設計: BOM の読み飛ばしと `\r` の除去を外す

- 日付: 2026-10-23
- フェーズ: テスト設計(作成は `test/drop_bom_and_cr`)
- 対象: `droneflow/parsing/map_reader.py`(`encoding="utf-8"`、`rstrip("\n")`)
- 参照した決定: `docs/decisions.md` 2026-10-23「BOM の読み飛ばしと、効いていない `\r` の除去を外す」

| ID | 前 | 後 |
|---|---|---|
| BM01 | BOM つきのマップが BOM なしと同じに読める | BOM つきのマップは `line 1: the first line must be 'nb_drones: <n>'` |
| BM02 | BOM と CRLF が重なっても読める | CRLF のマップ(BOM なし)が LF と同じ World になる(`\r` を消す処理を外しても、テキストモードが LF に直す) |
| BM03 | 先頭の BOM は1つだけ読み飛ばし、2つ目や途中の行の BOM はエラー | 先頭の BOM が2つでも1行目のエラー、途中の行の BOM はその行のエラー(期待値は同じ。docstring を直す) |
| BM04 | BOM つきのマップがアプリの入口から最後まで動く | BOM つきのマップはアプリの入口で `ParseError`(1行目)、標準出力は空 |
