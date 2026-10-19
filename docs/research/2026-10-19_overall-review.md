# 全体の構成確認と、意図どおりの実装かの点検

- 日付: 2026-10-19
- 依頼: 全体の構成を確認し、意図どおりに実装できているかを見る
- 対象: `develop` の c9202ed(`droneflow/` 全体、`fly_in.py`、`Makefile`、設定ファイル、README の例)
- 照合の基準: `docs/decisions.md`(全項目)、`docs/bugs.md`、`docs/roadmap.md`、`docs/research/2026-10-17_stage5-benchmark.md`
- コードは変更していない(分析のみ)

## 1. 実行して確かめたこと

| 項目 | 結果 |
|---|---|
| `pytest tests -q` | 569件すべて通過 |
| `flake8 .` | エラーなし |
| `mypy .`(課題 III.2 のフラグ) / `mypy . --strict` | どちらもエラーなし(74ファイル) |
| 配布マップ10枚(コメント行を除いた写し)と課題の例 | すべて完走。ターン数はベンチマークの最新表(2026-10-19 追記)と完全に一致 |
| README の2つ目の例(restricted) | 出力・まとめの行が README の記載と一致 |
| 到達不能のマップ | `error: goal 'g' is unreachable from 's'`、終了コード1 |

ターン数: linear 4 / fork 4 / capacity 4 / dead_end 8 / circular 10 / priority 8 / maze 13 / capacity_hell 16 /
ultimate 26 / impossible_dream 44 / 課題の例 7(すべて VII.7 の目標を達成、impossible_dream は参考記録45を下回る)。

## 2. 構成(層と依存の向き)

```
fly_in.py ─ cli.py(Args) ─ app.py(Application: 組み立てとエラー変換)
  parsing/   MapReader → LineTokenizer → MapValidator(+ map_format の仕様表、map_rules の規則) → World
  pathfinding/ DistanceMap(goal からのダイクストラ) ← Pathfinder(next_hops、到達不能の検出)
  simulation/ SimulationEngine ─ Scheduler(TurnLedger、ReservationTable、Evictor)
                              └ TurnResolver(検査と適用) → SimulationState
  output/    TurnLogPrinter(stdout)、RunSummary(stderr)
  visualization/ Visualizer(Protocol)、Composite、Terminal、Graphical、palette
```

- 依存は上から下への一方向で、循環はない。pygame の import は `graphical_view.py` に閉じている。
- 「決める」(Scheduler)・「検査して適用する」(TurnResolver)・「状態」(SimulationState)が分かれており、
  2026-10-16 の Stage 4 の API 決定どおり。継承は例外・Enum・Protocol を除くと `map_rules.py` の2つの ABC だけ。

## 3. 決定記録との照合(主なもの)

すべて決定どおりに実装されていた。食い違いは見つからなかった。

| 決定 | 実装箇所 | 判定 |
|---|---|---|
| `nb_drones` は物理的な1行目 | `map_parser.py:34`、`line_tokenizer.py:36` | 一致 |
| start/end の `zone=blocked` を `ParseError`(仕様表で宣言) | `map_format.py:210`、`LineSpec.build` | 一致 |
| 重複メタデータキーは `ParseError` | `line_tokenizer.py:92` | 一致 |
| start/end の `max_drones` は無視するが値は検査 | `ZoneBuilder`(値は `to_positive_int` を通る) | 一致 |
| goal からのダイクストラ、入るゾーンの `turn_cost` が重み | `distance_map.py` | 一致 |
| `next_hops` は「入るコスト+距離」で比較、priority は同点の中だけ | `pathfinder.py:98-101` | 一致 |
| 到達不能は `Pathfinder` 構築時に `UnreachableGoalError` | `pathfinder.py:55-57` | 一致 |
| 容量は最終負荷、接続は向きを区別しない | `turn_resolver.py` `_check_zones` / `_check_links` | 一致 |
| restricted の到着ターンは接続容量に数えない | `turn_resolver.py:154`、`TurnLedger.link_free` | 一致 |
| 自己ループ経由の「移動」を拒否 | `turn_resolver.py:135` | 一致 |
| 判断順: 距離 → 優先ルート → ID | `Scheduler._decision_key` | 一致 |
| 予約表は Scheduler が持つ、予約は検査しない、立ち退きは最後の手段、規則6' | `scheduler.py`、`evictor.py` | 一致 |
| 無限ループ検出(誰も動かない・ターン上限) | `engine.py:91-103` | 一致 |
| stdout はターンログだけ、他は stderr | `app.py`、`TurnLogPrinter` | 一致 |
| エラーの扱い(終了コード 1 / 2 / 130、パイプ、最後の砦) | `fly_in.py` | 一致 |

`Scheduler` の「このターンに立ち退きが決まった機は待つ」(`scheduler.py:107-110`)は、立ち退き先が常に
距離が真に小さいゾーンで、その在室機は判断順で先に処理済みのため、実際には働かない防御の分岐と読める。

## 4. 気づいた点(バグではないもの)

1. **`main` が初期のスケルトンのまま**(3コミット)。提出物を `main` に反映する作業は未着手。反映の前に、
   2026-10-19 の決定どおり README の「Testing and quality」、`Makefile` の `test`、`requirements.txt` の pytest、
   `setup.cfg` の tests 向け設定を直す必要がある。
2. **合成優先の方針との差**: `map_rules.py` の `ZoneRule` / `ConnectionRule` が ABC の継承で種類の振り分けをしている。
   ロードマップのタスク4(リファクタリング)の候補。
3. **エンジンが具体クラスに依存**: `SimulationEngine` の引数の型が `Scheduler`(具体クラス)。テストは monkeypatch で
   差し替えている。`decide_moves` だけの Protocol にすると差し替えが型の上でも素直になる(タスク4の候補)。
4. **実行経路で使われないもの**: `Pathfinder.best_route` / `Route`、`TurnLogFormatter.emit`、`DroneStatus.WAITING`。
   いずれも既知(archify の図のカード、2026-10-16 の決定)。残すか消すかはタスク4で判断できる。
5. 既知の未対応バグ: 空ファイルのエラーが `line 0`(`docs/bugs.md` 2026-10-16、軽微)。今回も再現した。
6. 決定済みのリスク(再掲のみ): 配布マップはそのままでは1行目で `ParseError` になる(2026-10-18 に README で
   制約を説明する方針で確定済み)。評価の場で説明が要る。

## 5. 確認していないこと

- `graphical_view.py`(602行)と `terminal_view.py` の後半は詳しく読んでいない(テストは通過)。ロードマップのタスク1で見直す予定。
- `make` 自体での実行(このセッションでは Windows の venv で各コマンドを直接実行した)。
