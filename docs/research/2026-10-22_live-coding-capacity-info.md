# ライブコーディングの準備: `--capacity-info`

- 日付: 2026-10-22
- 依頼: ライブコーディングの作業について docs に書く。ブランチを切り、編集する箇所が見えるようにする。
- 出典: 評価シート(`revie_case/イントラプロジェクト フライイン編集.pdf`)。整理は `docs/research/2026-10-16_review-test-patterns.md`。
- 関連する決定: `docs/decisions.md` 2026-10-21「全体レビュー…」の7(`Move.connection` を持たせる)、
  2026-10-22「ライブコーディング(`--capacity-info`)と重なる内容を外す」
- **この文書は手順と編集する箇所だけを書く。答えのコードは書かない**(評価の場で本人が書く作業のため)。

## 課題

- 評価の場で、**10分以内**に `--capacity-info` フラグを追加する。
- 各ターンに、ゾーンと接続の使用状況を出す: 「ゾーンX: Y/Z ドローン」「接続AB: Y/Z 容量使用」。
- 評価で使うマップは配布マップと違うことがある。

## 練習用のブランチ

- `feature/capacity_info`(`test/trim_run_file` から切った)。編集する箇所に `LIVE CODING (--capacity-info)` という印のコメントだけを入れてある。
  実装は入っていない。
- 編集する箇所の一覧: `git grep -n "LIVE CODING"`。印を入れた差分: `git show feature/capacity_info`。
- **このブランチは develop / main にマージしない**(印のコメントは提出物に要らない)。練習は、このブランチからさらに切ったブランチで行い、
  終わったら捨ててよい。

## 使えるもの(すでにあるもの)

| 欲しいもの | どこにあるか |
|---|---|
| そのターンの移動 | `TurnObserver.render(state, moves)` の `moves`(`list[Move]`) |
| 移動で使った接続 | `Move.connection_name`(出発の移動だけ。着陸は `None`) |
| ゾーンの在室数 | `SimulationState.occupancy(name)`(飛行中の機は `reserved(name)` に別に数える) |
| ゾーンの容量 | `Zone.capacity`(start/end は `None` = 無制限) |
| 接続の容量 | `Connection.max_link_capacity` |
| ゾーン・接続の一覧(宣言順) | `state.network.zones`・`state.network.connections` |
| 毎ターン呼ばれる口 | `TurnObserver`(`begin`・`render`・`close`)。`TurnLogPrinter` が見本 |
| 観測者を足す場所 | `Application.run` の `observers` のリスト(`ObserverGroup` に渡す) |

## 手順(目安 10分)

1. `cli.py`: `Args` にフィールドを1つ足し、`build_parser` に `--capacity-info`(`store_true`)を足し、`parse_args` で渡す。(2分)
2. 新しい観測者のクラスを書く(置き場所の候補は `droneflow/output/`)。`render` で、
   - ゾーン: 容量のあるゾーンごとに「在室数/容量」を作る。
   - 接続: その `moves` のうち `connection_name` が同じものを数え、「使った数/`max_link_capacity`」を作る。
   - 1ターン分を書き出す。`begin` と `close` は何もしなくてよい。(5分)
3. `app.py`: フラグが立っていれば、`run` の `observers` にそのクラスを足す。(1分)
4. 動かして確かめる(下の「確かめ方」)。(2分)

## 注意する点

- **標準出力にはターンログだけ**(課題の出力形式。README にもそう書いている)。報告は標準エラー出力(`Application.err`)に書く。
  `--visual none` でも出るように、表示(views)ではなく `observers` に足す。
- 接続の容量を使うのは**出発したターンだけ**。restricted へ向かう機は、出発のターンに `connection_name` を持ち、
  次のターンの着陸の `Move` は `None`。だから「そのターンの `moves` の `connection_name` を数える」で、規則(`TurnResolver`)と同じ数え方になる。
- 飛行中の機は、まだゾーンの在室数に入らない(着陸したターンから数える)。到着予定も出すかは自分で決める(グラフィカル表示は `+N`)。
- start / end は容量が無制限(`capacity is None`)。出さないか、`Y/-` のように書くかを決めておく。blocked のゾーンは入れないので出さなくてよい。
- 毎ターン全部のゾーンと接続を出すと長くなる。使われているものだけ出すか、全部出すかを決めておく(課題の文言は「各ターンに」だけ)。
- `make lint`(flake8 と mypy)を通すこと。型注釈と docstring を忘れない。

## 確かめ方

```sh
python fly_in.py maps/subject_example.txt --visual none --capacity-info
python fly_in.py maps/subject_example.txt --visual none --capacity-info 2>/dev/null   # stdout がターンログだけか
make lint
```

課題の例のターン2では、restricted の roof1 に D2 が着陸し、D4 が hub-roof1 を出発する。roof1 は在室1/容量1、
hub-roof1 は使用1/容量1 になるはず(グラフィカル表示の `1/1 +1` と比べるとよい)。corridorA-tunnelB は容量2。
