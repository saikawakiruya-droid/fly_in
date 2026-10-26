# 可読性の指針の採否と実装結果

- 日付: 2026-10-25
- 目的: 「命名や構造によって理解しにくい」という指摘を受け、文献調査で得た指針 G-1〜G-16
  (`docs/research/2026-10-25_readability-literature.md`)をこのコードに取り入れるかを判断し、採ったものを実装・確認した記録。
- 流れ: 調査(指針を1件ずつ)→ 判断(指針1件に1人。箇所ごとの採否と理由)→ 実装 → 確認 → コミット(1指針 = 1コミット)。
  残すかどうかはユーザーが決める(要らないものは revert)。
- ブランチ: `feature/readability_guidelines`(develop 53fc3a2 から)。develop へのマージ済み(f282742)。
- 確認の基準(全コミットで共通): pytest 662 件、flake8、mypy(課題のフラグ / --strict)、79 枚のマップの出力が変更前(53fc3a2)と一致。
  matplotlib_window に触れたものは、描画の結果(axes の全要素)も変更前と一致。

## 採ったもの

| 指針 | コミット | 変更 |
|---|---|---|
| G-3 略語 | 5365b22 | `Application` の `out`/`err` → `stdout`/`stderr`、parsing の `src` → `line`、`_wrap` の `sep` → `separator` |
| G-5 モジュール名 | 9d9f653 | `output/formatter.py` → `turn_log_formatter.py`、`palette.py` の要約を両方の表示向けに |
| G-1 名前と中身 | 0cb205d | `Position.zone` などゾーン名の str を `zone_name` に(2026-10-22 の「zone は Zone」の漏れ) |
| G-7 関数の長さ | 18d64f2 | `MapScene.show` から `_drone_groups`、`__init__` から `_draw_zones` を切り出し |
| G-6 抽象度 | e4c6067 | `MapScene`(`_route_connections`・`_draw_zone_names`・`_highlight_busy_links`・`_draw_drones`・`_draw_title`)、`TurnResolver._zone_changes`、`DetourPolicy._forget_from`、`Scheduler._order_due_moves`、`Application._observers`・`_print_summary` |
| G-2 1概念1語 | 62e0790 | `zone_name_by_drone`・`zone_names`、pathfinder の距離 `here`/`there` → `distance`、`_costed_moves` → `_costed_hops`、Reservation の変数 → `reservation(s)`、`arrive` → `arrive_turn`、HopTaker の `here` → `from_zone`、`RunSummary.turns`/`drones` → `total_turns`/`nb_drones` |
| G-9 定数 | 43858c9 | scene の `1.15` → `_SQUARE_REACH`、terminal の `"  "`・`8` → `_ROW_INDENT`・`_COUNT_WIDTH` |
| G-11 docstring の1行目 | 7ade24d | `Network`・`add_connection`・`MapValidator`・`LineTokenizer` の要約(確認で1回不合格: 要約が2行に折れていた → 1行に) |
| G-10 コメント | 4c1d4f3 | `to_text` の docstring に、ある理由と色名を検査しないことを書いた |
| G-13 公開/非公開 | 33e4212 | scene の `zone_color` → `_zone_color` |
| G-15 変数のスコープ | 929cd81 | `Scheduler` の使われていない属性 `network`・`pathfinder` を削除 |
| G-16 並び順 | 49d2b41 | `DetourPolicy`・`Scheduler` の非公開メソッドを呼ぶ順に並べ替え |

## 採らなかったもの

| 指針 | 理由 |
|---|---|
| G-4 汎用名 | 候補7件はスコープが数行、または型名・関数名・慣例が意味を補っている |
| G-8 素通しの層・情報の漏れ | 候補10件は過去の決定で意図した委譲(Pathfinder→DistanceMap 2026-10-16、TurnLogFormatter 2026-10-03/18、ObserverGroup)か効果が小さい |
| G-12 フラグ引数 | 当てはまる箇所なし(`may_evict` は名前のある変数で渡している) |
| G-14 型名・単位 | 型名を重ねた名前なし。`turn_number`(2026-10-21 に語彙を残すと決定)・`delay`(docstring に秒と記載)は見送り |

## 範囲外として残った気づき(2026-10-26 に同じ流れで処理)

| 気づき | 判断 | コミット | 内容 |
|---|---|---|---|
| F-1 palette の本文 | 直す | d88ff1e | 端末だけを前提にした文を「表に無い名前は ``rgb`` が None を返し、各表示が自分の既定に戻す」に |
| F-2 `_draw_zones` の要約 | 直す | fefd90d | 「Draw each zone in its shape, fill and outline color.」に(塗りが種類を表すように読め、形が抜けていた) |
| F-3 `SimulationState.drones_at` | 直す | 29f866f | 本体から使われていないので削除(2026-10-21 の決定2の見落とし)。S03・S04 の確かめる行2行も削除。D1 の位置は test_turn_resolver・test_engine で確かめている |
| F-4 `Zone.has_unlimited_capacity` | 直さない | — | 食い違うのは max_drones の無い hub だけで、パーサーが既定値 1 を入れるので作られない。読む側は `capacity` だけで、その docstring が前提を説明している |

- ブランチを develop にマージした(f282742、2026-10-26。ユーザーの許可)。D: ドライブが外れたため、途中からワークツリーを `.claude/worktrees/readability` に移した(コミットは失われていない)。

## 進め方で起きたこと

- 最初は調査担当にコードを調べさせたが、ユーザーの指示で文献調査に切り替えた。調査担当には優先度・指針同士の比較をさせない。
- 採否の判断役を置いていなかった(ユーザーの指摘)ため、判断担当を指針ごとに置いた。
- 比較の基準で、配布マップ10枚が先頭のコメントのため1行目のエラーで止まっていた(パーサーは 2026-10-16 の決定どおり)。
  先頭のコメントを除いた写しで基準を取り直し、それまでのコミットも含めて一致を確かめた。
