# 2026-10-22 会話ログ: GitHub issue の整理と会話ログのルール

- 開始: 2026-10-22 11:15 頃

## GitHub issue の確認と整理

- 依頼1: issue はなくなっているか。→ Stage 0〜10 の11件がすべて OPEN のまま残っていた。
- 依頼2: 随時閉じていなかった理由を確認し、終わっているものを閉じる。
  - 理由: issue は 2026-09-05 の実装計画(`docs/research/2026-09-05_implementation-plan.md`)で登録しただけで、
    閉じる手順をどこにも決めていなかった。PR を使ったのは Stage 2 の #12/#13 だけで、本文に `Closes #3` が無く自動で閉じなかった。
    その後はローカルのブランチを develop にマージする流れになり、進捗は `docs/research/` の workflow / test-design と
    `decisions.md`・`bugs.md` で管理したため、issue を参照する場面が無かった。
  - 確認: 全 Stage が完了(Stage 8 の検証では全マップが目標内・違反なし、Stage 10 の目標も達成、README 日英あり)。
  - 対応: #1〜#11 を、完了の根拠をコメントに書いて completed で閉じた。#3 には未対応の軽微な点(空ファイルで `line 0`)を書き添えた。
- 決定事項: なし(今後 issue を使うかどうかは未決)。変更ファイル: 本ログのみ。
- 依頼3: issue を閉じるルールを CLAUDE.md に足す。→ 「GitHub issue の運用」節を追加し、decisions.md に記録した。
  `../cordection` はリモートも issue も無いので変更なし。変更ファイル: `CLAUDE.md`、`docs/decisions.md`、本ログ。
- 依頼4: 会話ログを「開始日のフォルダ + セッションごとのファイル」にし、日付が変わったら記録するようにする。
  - cc_space 共通ルール(`cc_space/CLAUDE.md` の「会話ログ・意思決定の記録」)の置き場所を
    `docs/conversation_log/YYYY-MM-DD/NN_<topic-slug>.md` に変え、日付をまたいだら記録して `## YYYY-MM-DD(日付変更)` の見出しを立てる規則を足した。
  - fly_in の 2026-10-22.md を、このフォルダの3ファイル(セッションごと)に分けた。2026-10-21 以前のログはそのまま。
  - 変更ファイル: `cc_space/CLAUDE.md`(git 管理外)、`docs/conversation_log/2026-10-22/`、`docs/decisions.md`
