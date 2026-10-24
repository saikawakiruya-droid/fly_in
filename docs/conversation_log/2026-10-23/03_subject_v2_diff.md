# 課題PDF v2.0 の変更点

開始: 2026-10-23

## 依頼

課題PDFが更新された(`new_fly_in.pdf`)ので、変更点を教えてほしい。

## 作業の要点

- `fly_in.pdf`(v1.6)と `new_fly_in.pdf`(v2.0)をテキスト化して差分を取った。
- 変更点: 制約違反は即不合格、同時移動と容量解放の明確化、restricted 接続の到着ターンでの解放、到達不能マップの検出、
  ベンチマークを「目標」から「最適値」へ変更、ボーナスは the_impossible_dream を 43 で解くことだけに。
- 今の実装との照合: 必須9枚はすべて最適値ちょうど。the_impossible_dream は 44(最適値 43)。

## Q: 各ドローンの動きはターン開始時の状態から決めているか(1機ずつの計算になっていないか)

- 決める手順は1機ずつ(`Scheduler.decide_moves` が `ZoneRanking` 順に `_decide` を呼ぶ)。ただし:
  - 状態(`SimulationState`)は判断中に変わらない。各機の居場所はターン開始時のもの。同じターンの先の判断は
    `TurnLedger` に「出る・入る」の数として記録されるだけ。
  - 1機に指示は高々1つ(`TurnResolver._check_orders`)。決めた指示は後から変えない。`Evictor` が作るのは
    後のターンの予約だけで、すでに動いた機は `PositionBoard` 上で元のゾーンにいないので立ち退きの候補にならない。
  - `TurnResolver` は全部の指示をまとめて、開始時の数+増減の最終値で検査し、全部合法な時だけ一度に適用する(同時移動)。
- 1機ずつなのは、PDFが許している「同じターンに空いた分を使う」を先読みするため。v2.0 の規則に反していないと判断した。
- 限界(違反ではない): 先に判断した機は、後で判断する機が出ていく分を見ない(`TurnLedger` の docstring)。
  ゴールに近い順に判断してこれを抑えている。

## Q: the_impossible_dream を 43 に縮めるには

- 今の 44 は、ターン21にゴール到着が0機の穴が1つあるため。元はターン13の D3 の待ち。立ち退きの予約ができるだけ遅いターンになり、
  予約済みの出発を早められない(`Evictor._candidate`)。
- 立ち退きの規則を直す試作(A・B)は 44〜45 で効かなかった。
- 優先度つきの時空間計画(1機ずつ全行程を(ゾーン, ターン)の上で最早到着の探索で確定させる)の試作で **43**。
  配布マップ10枚はすべて最適値ちょうど、課題の例 5、revie_case 25枚は今と同じ合計 343。毎ターン `TurnResolver` で検査済み。
- 詳細と実装の論点: `docs/research/2026-10-23_impossible-dream-43.md`

## 決定

- the_impossible_dream を 43 にする変更は行わない(ユーザー判断、`docs/decisions.md` 2026-10-23)。

## 作成したファイル

- `docs/research/2026-10-23_subject-v2-changes.md`
- `docs/research/2026-10-23_impossible-dream-43.md`

## 作業(ユーザーの指示)

- R04/R05 を v2.0 の最適値に合わせた(`test/subject_v2_optimum`、c89d4b4。develop へのマージは未)。
- `new_fly_in.pdf` を `fly_in.pdf` に置き換えた(旧 v1.6 は会話中のみ scratchpad に写しあり)。

## 未決事項

- `test/subject_v2_optimum` を develop にマージするか(ユーザーの許可待ち)。
