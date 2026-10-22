# 2026-10-22 会話ログ: 後回しタスクの洗い出し

- 開始: 2026-10-22

## 後回しにしていたタスクの洗い出し(develop)

- 依頼: 後回しにしていたタスクを見つけてほしい
- 回答要点(docs/ の「未決・後で・未対応・未着手」を検索し、解決済みの追記を除いた):
  - `docs/roadmap.md` の4タスク(ビジュアライズの改善、パーサーの単体実行、移動ロジックの単体実行、リファクタリング)が「未着手」のまま。
    4 は `feature/refactor_review` で実質済みだが、表が更新されていない
  - bugs.md 2026-10-16「空ファイルのエラーが `line 0`」が未対応(軽微)
  - `_tmp/` の図(archify 等)と `_tmp/huge_mesh/` の昇格判断が未決(2026-10-16・10-19)
  - 本ファイル(2026-10-22.md)が未追跡のまま
- 決定事項: なし。変更ファイル: 本ログのみ


## パーサーと移動ロジックの単体実行(feature/stage_files・test/stage_files)

- 依頼: 「2,3,4 を行う」。段階の間で渡すオブジェクトの中身が見えるようファイルを経由し、移動は1ターンごとに実行できるように。
  オプションとして用意し、追加機能として README に加える。
- 確認(質問への回答): 2・3 はロードマップの 2・3、4 は前回の一覧の 4(会話ログのコミット)。形式は JSON(標準ライブラリ)。
  1回の起動で1ターンだけ進める形は「難しそうなのでしなくていい」。
- 4 は、別のセッションがログを新しい形式(このフォルダ)に分けてコミット済みだったので、作業なし。
- 作業(`feature/stage_files`): `--parse-only FILE`・`--from-world`・`--save-run FILE` を追加(`droneflow/interchange/`)。
  README 両版に「追加機能」の節。1ターンずつ見るのは `--from-world --step` と `--save-run` の各ターンの記録で代える。
- 確認: 正常に終わる配布マップ・課題の例・revie_case の 25 枚で、直接の実行と `--parse-only` → `--from-world` のターンログが一致。
- テスト(設計 `docs/research/2026-10-22_test-design-stage-files.md`、作成 `test/stage_files`): JO・WF・RR・SC・SA・SM の 73 件を追加。
  pytest 818件成功、flake8・mypy(両方)問題なし。
- バグ: SA05 で `--from-world` が表示名(`map_arg`)でファイルを開く不具合を発見し、`feature/stage_files` で修正(`docs/bugs.md` 2026-10-22)。
- 決定: `docs/decisions.md` 2026-10-22「パーサーと移動ロジックを、JSON ファイルを経由して単体で動かせるようにする」。
  `docs/roadmap.md` の 2・3 を実装済み、4 を実質完了に更新。
- 未決: `test/stage_files`(`feature/stage_files` を含む)の `develop` へのマージ(ユーザーの許可待ち)。
  main への反映(README の追加機能と `droneflow/interchange/` を含む)は別作業。
- 作成・変更したファイル: `droneflow/errors.py`、`droneflow/cli.py`、`droneflow/app.py`、`droneflow/interchange/`(新規)、
  `README.md`、`README.ja.md`、`tests/interchange/`(新規)、`tests/test_cli.py`・`test_app.py`・`test_fly_in.py`、`tests/README.md`、
  `docs/decisions.md`、`docs/bugs.md`、`docs/roadmap.md`、`docs/research/2026-10-22_workflow-stage-files.md`・`2026-10-22_test-design-stage-files.md`

## 成果物の確認と、表示の単体実行

- 依頼: それぞれの実行の成果物を確認したい → 課題の例で `_tmp/stage_files/` に出力(world.json、run.json、stdout/stderr)し、
  中身を表にして説明。直接実行と `--from-world` のターンログはバイト単位で一致。
- 質問: 表示の単体実行はできないか → できない(表示はエンジンの observer)。記録を再生する案を提示したが、ユーザー判断で見送り。
  スケジューラーの実行に `--visual`・`--step` を付ければ表示でき、`--save-run` と併用しても記録は同じことを確認。
- 決定: `docs/decisions.md` 2026-10-22「表示の単体実行(記録の再生)は作らない」
- 未決: `test/stage_files` の develop へのマージ(ユーザーの許可待ち)
- ユーザーの許可を得て `test/stage_files` を develop にマージ(2987ed9)。pytest 818件成功、flake8・mypy 問題なし。開いている issue はなし。
  roadmap の 2・3 を完了に更新。main への反映は後回しにし、次はロードマップ 1(ビジュアライズの改善)を先に行う(ユーザー判断)。

## ビジュアライズの改善(ロードマップ 1)の着手: 色・透明度・重なりの調査

- 依頼: ビジュアライズの改善を先にやる。色の扱い、透明度のパラメータが使えるか、同じ座標のゾーンの扱い、接続が重なるときの描き方を知りたい。
- 作業: 配布マップと検証用マップをヘッドレスで描画(`_tmp/visual_review/`)。調査記録 `docs/research/2026-10-22_visualization-colors-overlaps.md`。
- 回答要点: 色は名前の表 → pygame の色名 → 灰色。透明度は使えない(RGB だけ)。同じ座標のゾーンは後のものが前を隠す(名前・数字・ドローンが重なる)。
  接続は宣言順の直線で、他のゾーンの上を通る接続は区別できない。
- 未決: どの改善を行うか(調査記録の「改善の候補」1〜4。ユーザー判断待ち)

## ボーナスの達成状況の確認

- 質問: ボーナスをやった状態になっているか。
- 確認(develop、cd4d1ed 以降): ボーナス(課題 IX)は「配布マップ全部で目標以下」と「challenger を45ターン未満」。配布マップ10枚を実行し、
  easy 4/4/4(目標 6/8/6)、medium 8/10/6(12/15/12)、hard 13/16/26(30/35/45)、challenger 44(45未満)で、両方とも達成。
- 決定事項: なし。変更ファイル: 本ログのみ。

## ビジュアライズの改善 1回目(ラベル)と、ライブコーディングとの重なりの整理

- 依頼: `2/1` の紛らわしさと下の行のはみ出しを直す、start/end の名前に () を付ける。線が黄色い理由(overlap_t1 でターン1なのに2回動いて見える)。
  - 作業(`feature/visual_labels`): ゾーンの数字を「在室数/容量 +到着予定」(`1/1 +1`)に、下の行は `... +K more`、名前に ` (start)`/` (end)`。
    文字の部品を `droneflow/visualization/labels.py`(pygame 不要)に分けた。テストは `test/visual_labels`(VL01〜VL14、834件成功)。
    テスト設計の VL11 は設計の誤り(全体が幅に収まっていた)を作成時に訂正。
  - 回答: 黄色の線はそのターンの移動の軌跡。overlap_demo の D2・D3 は s-c を通ったが、s-c が b の下を通る直線なので s→b→c と2回動いたように見える
    (重なる接続の問題。改善の候補2)。
- 質問: ライブコーディングの内容を含めていないか(表記の数が気になる)。
  - 回答: 評価シートの `--capacity-info` と、`--save-run` の `zones`・`connections`(今日の実装)がほぼ同じデータ。README と docstring にもヒントがあった。
    表示のゾーンの数字は Stage 7 から。
  - ユーザー判断(案2): `run.json` から `zones`・`connections` を外し、README と docstring のヒントも消す(`Move.connection` は残す)。
    `feature/trim_run_file`(実装)・`test/trim_run_file`(RR02〜RR05 の変更、818件成功)。決定は `docs/decisions.md`。
  - 手順書 `docs/research/2026-10-22_live-coding-capacity-info.md`(答えのコードは書かない)。練習用ブランチ `feature/capacity_info` に
    `LIVE CODING (--capacity-info)` の印を5か所(`git grep -n "LIVE CODING"`)。**このブランチはマージしない。**
- 未決: `test/visual_labels`・`test/trim_run_file` の develop へのマージ(ユーザーの許可待ち)。重なる接続(弧にするなど)・同じ座標のゾーン・透明度の改善をするか。
## ビジュアライズの改善 2回目(重なる接続を弧に、同じ座標のゾーン)

- 依頼: 重なる接続を弧にする、同じ座標のゾーンの改善を進める。終わったら WSL でテストマップに対して全体・部分実行する。
  あわせて、線が黄色い理由と、overlap_t1 でターン1なのに start から2回動いて見える理由を知りたい(前回の説明が伝わっていなかった)。
- 作業(`feature/visual_overlaps`、`test/visual_labels` から切った): 同じ座標のゾーンを円周上に並べる、他のゾーンの上を通る接続は2次ベジェの弧、
  飛行中の機・`x2` は弧の真ん中、軌跡は使った接続の弧に沿う。幾何は `droneflow/visualization/geometry.py`(pygame 不要)。
  start/end の名前の幅に `(start)` を数えないように変更(challenger で `s~ (start)` になったため)。
- 性能: 1万ゾーンのメッシュで配置に225秒かかった。原因は既存の最近接距離の全組み合わせ(O(n²))を2回呼んだこと。x で並べて打ち切る方法に置き換えた。
- テスト(`test/visual_overlaps`): GE01〜GE19・VO01〜VO05、VG04・VL03 を変更。pytest 858件成功、flake8・mypy 問題なし。
- 決定: `docs/decisions.md` 2026-10-22「重なる接続を弧にし、同じ座標のゾーンをずらす」
- WSL での全体・部分実行: 配布マップ・revie_case・課題の例・overlap_demo で、部分実行の検査 194/194 成功、make lint/test も成功
  (`docs/research/2026-10-22_wsl-full-partial-runs.md`)。途中で、1万ゾーンの配置が遅い問題(避ける距離に上限)を直し、GE20 を追加(859件成功)。
- 説明: 黄色の線はそのターンに動いた機の軌跡(接続は灰色)。overlap_t1 の D2・D3 は s→c を1回で動いたが、s-c が b の真下を通る直線だったため
  s→b→c に見えた。弧にしたことで解消。
- 未決: `test/visual_labels`・`test/trim_run_file`・`test/visual_overlaps` の develop へのマージ(ユーザーの許可待ち。overlaps は labels を含む)。
- ユーザーの指摘・依頼と対応:
  - 「曲げても結局重なっていないか」→ 重なっていた(一直線の5ゾーンで弧が全部下に束)。先に決めた弧からも離し、上側を先に試すよう修正。
  - 「自己接続は試したか」→ WSL の実行(P06)では通っていたが、表示では描いていなかった。ゾーンの上の小さな輪として描くよう修正。
  - 「省略された名前はカーソルを合わせると見えるか」→ 見える(詳細の箱に名前・役割・種類・色・在室数・ID)。`_tmp/visual_review/hover_challenger_t10.png`。
  - 「同じ座標のドローンは個数表記でよい」→ 2機以上は件数の札1つに変更。
  - テスト: GE21〜GE23・VO06・VO07 を追加、865件成功。
  - 未決: 形の見た目(アンチエイリアスなど)、拡大縮小・移動(超巨大マップ向け)の設計

## 拡大縮小・なめらかな描画と、develop へのマージ

- 依頼: 拡大縮小(画面の大きさは固定、ゾーンの大きさは一定)とアンチエイリアスを進め、検証まで終わったらマージ。
- 作業(`feature/visual_zoom`・`test/visual_zoom`): `Camera`(倍率とずれ)、ホイール・ドラッグ・`f`、縮小時の描き分け、画面外を描かない、
  `aacircle`/`aalines`。README 両版のグラフィカル表示の節を更新。テスト CA01〜CA08・VZ01〜VZ08(VZ01 が倍率の上限の実装の誤りを発見→修正)。
- 検証: develop に `test/trim_run_file` と `test/visual_zoom` を合わせた状態で、Windows(884件)と WSL(全体・部分実行 197/197、make lint/test)。
- マージ: ユーザーの許可(「検証まで終わったらマージ」)により develop を 5922314 まで進めた。ロードマップ 1 を完了に。
- 次の依頼: Windows 対応を消してコードが減るなら減らす。
- Windows 対応の削除(`feature/drop_windows_support`・`test/drop_windows_support`): `fly_in.py` の `_is_closed_pipe`(Windows の EINVAL)、
  Makefile の `Windows_NT` の分岐、README 両版の一文、テストの AM06 の einval・AM07 を削除。コードは差し引き22行減。
  端末表示の ASCII(元は Windows の文字コード対策)は、外してもコードが減らないので残した。決定は `docs/decisions.md`。
  検証: Windows で pytest 878件、WSL で make lint/test(878件)・全体/部分実行 197/197、実際に `| head -1` でパイプを閉じて
  stderr なし・終了コード 1。
- 未決: `test/drop_windows_support` の develop へのマージ(ユーザーの許可待ち)
- マージ(ユーザーの許可「ほかの作業とともにマージ」): `test/drop_windows_support` と、別セッションの `feature/scheduling_package`
  (Scheduler の部品を `simulation/scheduling/` へ移す整理。検証済みでマージ待ちだった)を、scratchpad の作業ツリーで develop に合わせて
  検証し、develop を 3b40b46 まで進めた。別セッションの作業ツリー(D:)には触れていない。
- 依頼: 全マップの部分実行を見たい → `_tmp/partial_runs/summary.md`(一覧)と各マップの成果物を WSL から持ち帰った。
- 残っているもの: `feature/capacity_info`(練習用。マージしない)、main への反映、VG08 の不安定さの調査(bugs.md)。
