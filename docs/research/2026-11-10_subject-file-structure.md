# 課題PDF(v2.0)のファイル構造に関する記述(2026-11-10)

- 依頼: PDF にファイル構造についての記述があるらしいので確認する。
- 対象: `fly_in.pdf`(v2.0)を `pdftotext -layout` でテキストにして、structure / file / folder / root などで検索した。

## 記述のある箇所

| 章 | 記述 | 今の main |
|---|---|---|
| X Submission | "Place all your files at the root of your repository." | `fly_in.py`・`Makefile`・`README*`・`droneflow/`・`maps/` などがすべてリポジトリ直下。満たす |
| VIII Readme | README.md をリポジトリのルートに置く | `README.md`(と `README.ja.md`)が直下。満たす |
| III.2 Makefile | install / run / debug / clean / lint(指定フラグ)、lint-strict は任意 | すべてある |
| III.3 | テストプログラムは作るが提出も採点もされない。`.gitignore` を置く | tests は main に含めない(2026-10-19 の決定)。`.gitignore` あり |

- 決まったファイル名(メインスクリプトの名前など)や、ディレクトリ構成の指定は無い。`run` は "the main script of your project" とだけある。
- "Place all your files at the root" は v1.6 にもあった文(v1.6 → v2.0 の差分に出ていない)。
  `docs/research/2026-09-05_foreword-ja-and-requirements.md` でも「Gitリポジトリのルート直下に全ファイルを配置」と整理済み。

## 読み方

- 42 の課題の定型文で、「リポジトリの中にさらにプロジェクト用のフォルダを作って、その中に置かない」という意味と読むのが普通。
  サブパッケージ(`droneflow/`)を禁じる文ではないと考える。
- 文字どおり「すべてのファイルを直下に(サブディレクトリなし)」と読む評価者がいる可能性はゼロではない。
  その場合に問われうるのは `droneflow/` と `maps/`。PDF にはそれ以上の根拠が無いので、今の構成を変える必要は無いと判断する。

## 追記(2026-11-10): ユーザーの判断で、ソースファイルをすべて直下に置くことにした

上の「今の構成を変える必要は無い」という判断はとらず、文字どおり「ソースファイルはすべて直下」と読むことにした
(`docs/decisions.md` 2026-11-10)。`droneflow/` をやめ、ファイル名は持ち主の名前で始める形にした(ブランチ `feature/flat_layout`)。
