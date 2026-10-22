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
