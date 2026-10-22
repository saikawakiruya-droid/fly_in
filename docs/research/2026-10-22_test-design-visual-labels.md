# テスト設計: グラフィカル表示のラベル(ビジュアライズの改善 1回目)

- 日付: 2026-10-22
- フェーズ: **テスト設計**(作成は `test/visual_labels`)
- 対象: `droneflow/visualization/labels.py`(`zone_title`・`fit_text`・`load_label`・`fit_items`)。`graphical_view.py` はこれらを呼ぶだけ。
- 参照した決定: `docs/decisions.md` 2026-10-22「グラフィカル表示のラベルを直す」1〜4
- 方針: pygame を使わない(`tests/visualization/test_labels.py`)。幅は「1文字 = 1」の偽の測り(`len`)で測る。状態は `make_network`・`place` で作る。
  ID の接頭辞は **VL**。

| ID | 何を確かめるか | 入力 | 期待 |
|---|---|---|---|
| VL01 | hub の名前はそのまま | hub `roof1`、幅 20 | `"roof1"` |
| VL02 | start / end に `(start)` / `(end)` | start `s`・end `g`、幅 20 | `"s (start)"`、`"g (end)"` |
| VL03 | 長い名前は名前だけを切る | start `abcdefghij`、幅 12(suffix 8 文字、名前に 4) | `"abc~ (start)"` |
| VL04 | 切り方(`fit_text`) | `"abcdef"` を幅 6 / 4 / 0 | `"abcdef"` / `"abc~"` / `"a~"`(1文字と `~` は残す) |
| VL05 | 容量のあるゾーン: 在室数/容量 | `s-a a-g`(a cap 2)、D1 が a | `"1/2"` |
| VL06 | 到着予定は `+N` で分ける(roof1 の `2/1` の件) | `s-r r-g`(r restricted cap 1)、D1 が r、D2 が r へ飛行中 | `"1/1 +1"` |
| VL07 | 到着予定だけ | 同じマップで D1 が r へ飛行中 | `"0/1 +1"` |
| VL08 | start は在室数だけ、end は配達数 | 3機、D1 が g | start `"2"`、end `"1 in"` |
| VL09 | blocked は出さない | b が blocked | `None` |
| VL10 | 移動の一覧: 収まれば全部 | `["D1-a", "D2-b"]`、幅 9 | `"D1-a D2-b"` |
| VL11 | 収まらなければ `... +K more` | `["D1-a", … , "D5-e"]`(5件、全体で 24 文字)、幅 18 | `"D1-a ... +4 more"`(16 文字。2件残すと 21 で超える)。作成時に訂正: 当初の3件・幅 18 は全体が 14 文字で収まってしまう設計の誤りだった |
| VL12 | 1件も入らない | 同じ、幅 5 | `"... +3 more"`(幅を超えても残りの数は出す) |
| VL13 | 空 | `[]` | `"-"` |
| VL14 | 多いときも測る回数が少ない | 3,000 件、幅 200、測った回数を数える | 結果が幅以内で、残りの数と合わせて 3,000 件。測った回数が 20 回以下 |
