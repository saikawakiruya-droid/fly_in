# 2026-10-22 会話ログ: フォルダ構成の説明図(archify)

- 開始: 2026-10-22 20:45 頃

## フォルダ構成の図

- 依頼: フォルダを基準に、archify で説明ページを作る。
- 作業: archify の tree 図(左から右へ広がる形)で、develop の `a58ac33` 時点(後で `ce56156` に更新し、別セッションが追加した `docs/review_guide.md` を反映)のリポジトリを描いた。
  - `droneflow/` はファイル単位まで(各モジュールの1行目の docstring を元に短い説明をつけた)。`simulation/scheduling/` への整理を反映済み。
  - `tests/` と `docs/` はサブフォルダ単位に留めた(`tests/` は `droneflow/` と同じ構成のため)。
  - 補足カード: 「読み方」(線は包含だけ、①〜④は実行順)と「main と develop の違い」。
  - ガイドビュー: 実行の流れ順 / 1ターンの判断(scheduling) / develop だけにあるもの。
- 検証: archify の finalize(validate・deliver・check・browser-check)すべて成功。目視の確認はしていない。
  `ja` は archify の同梱言語に無いため、ビューアのボタン等は英語表示。
- 置き場所: 下書きとして `_tmp/folder-structure/`(`candidate.json`、`folder-structure.html`)。
- 未決: `docs/archify/folder-structure/` へ昇格するかどうか(ユーザーの判断待ち)。

## 2026-10-23(日付変更)

- 依頼: ファイルの置き場所を日本語で説明してほしい(前の回答が英語だった)。
- 回答: `_tmp/folder-structure/` の各ファイルの役割を日本語で説明した。昇格は引き続き未決。

## フォルダ単位の可視化

- 依頼: フォルダごとの単位で archify による可視化をする。意味を確認したところ「両方」(フォルダを箱にした全体図 + フォルダごとの図)を選択。
- 作業(develop `ce56156` 時点のコードから):
  - 全体図(architecture): フォルダを箱にし、import の向きを矢印で示した。models/ と errors.py はほぼ全フォルダが使うので矢印を省き、下の帯にした。
    交差が4か所と出たため配置を1回だけ直し、1か所まで減らした。
  - フォルダごとの図(class)9枚: droneflow/ 直下(app・cli・errors)、models、parsing、interchange、pathfinding、simulation(engine 側)、
    simulation/scheduling、output、visualization。他フォルダの型は「(他フォルダ)」をつけて境目に置いた。
    geometry・labels・palette は関数の集まりなので「(関数)」と書いて箱にした。
  - 元データは `_tmp/folders/` 配下(9枚分は scratchpad の生成スクリプトで作った)。
- 検証: 10枚とも archify の finalize(validate・deliver・check・browser-check)成功。目視の確認はしていない。
- 未決: `docs/archify/` への昇格(既存の stage1〜7 の図と内容が重なる部分がある)。

## archify の更新と図の作り直し

- 依頼: archify を更新し、過去の図をなくして、今の状態でフォルダ単位と機能単位で作り直す。
- 確認: 消す範囲は「docs/archify と _tmp の両方」、置き場所は「docs/archify/ に直接」をユーザーが選択。
- 作業:
  - archify 3.1.0 → 3.2.0(公式の archify.zip を取得し、更新情報の sha256 と一致することを確認して入れ替え。旧版は scratchpad に退避)。
  - 削除: `docs/archify/` の overview・stage1〜7、`_tmp/` の以前の図(architecture_overview・parsing_*・sequence-*・workflow-*)と今日の下書き。
    huge_mesh・partial_runs・stage_files・visual_review は図ではないので残した。
  - 作成: `docs/archify/folder-*`(11枚)と `docs/archify/feature-*`(7枚)。README 両版に一覧を追加。決定は `docs/decisions.md`。
- 検証: 18枚とも finalize 成功(sequence 2枚はノートの重なりを直して再実行)。目視の確認はしていない。
  folder-overview と feature-output に線の交差が残る(1か所・2か所)。
- 注意: 古い図の `git rm` は、別セッションのコミット `ecd68a4` に一緒に入った(未 push)。
