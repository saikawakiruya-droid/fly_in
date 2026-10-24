# matplotlib版と最小構成版の試作

開始: 2026-10-23

## 依頼

- 試したいことが2つ:
  1. 可視化に matplotlib を使った版を作る
  2. help や複雑なグラフィカル表示などをなくした、最低限の構成の版を作る
- 作業はサブエージェントに行わせる(ユーザーの明示的な指示。コードを書く範囲もこの2つの試作に限って解除)

## 作業

- develop(最新)から、それぞれ別の worktree・別ブランチでサブエージェントを並行して起動した
  - `feature/matplotlib_view`: pygame-ce の表示は残し、matplotlib の表示を新しいモードとして追加する方針
  - `feature/minimal_build`: 課題の必須要件だけを残す引き算。出力が develop と同じであることを確認させる
- どちらも試作のため、develop へのマージ・push はしない

## 方針の変更(matplotlib版)

- ユーザーの指示: matplotlib版では pygame を完全に取り除き、コードの見やすさを比べる
- 提出物の本命は pygame 版(develop)のまま。matplotlib版は比較用の試作
- エージェントに伝えた内容: `--visual graphical` / `both` の中身を matplotlib に置き換える、pygame 専用のモジュールと pygame-ce の依存を消す、可視化パッケージの行数を develop と比べて報告する

## 最小構成版の結果(`feature/minimal_build`)

- コミット 8 件(af14cc5〜1daefb3)。作者は noreply で、メッセージに個人情報なし(確認済み)
- 削除: グラフィカル表示一式と pygame-ce、JSON 連携(`interchange/`、`--parse-only` / `--from-world` / `--save-run`)、`--step`、`--delay`、
  `--visual`(ターミナル表示は常に出す)、要約行、`_GuardedView`、`FLYIN_DEBUG`、BrokenPipe の特別扱い
- 規模: 本体 50 ファイル・約 7,430 行 → 41 ファイル・4,620 行。テスト 823 件 → 641 件
- 検証: flake8・mypy(課題のフラグ / --strict)・pytest は通った。26 ケースで stdout と終了コードが develop と一致
- 配布マップがそのままだと ParseError になる件は、2026-10-16 の決定(nb_drones は物理的な1行目)どおりで、問題ではない
- 見てほしい判断: `| head` で BrokenPipe が「internal error」になる、要約行が無くなった、`--visual none` が無くなった(`2>/dev/null` で代わりになる)

## matplotlib版の結果(`feature/matplotlib_view`)

- コミット 4 件(486fa5e〜674da22)。作者は noreply で、メッセージに個人情報なし(確認済み)
- `--visual graphical` / `both` と `GraphicalVisualizer` のインターフェースは変えず、中身を matplotlib にした。pygame-ce → `matplotlib>=3.8`
- 規模: visualization 全体 2,210 → 1,782 行。グラフィカル表示固有の部分(graphical_view + camera)は 1,147 → 758 行(約34%減)
- 簡単になった点: ピクセル座標の計算と camera.py が不要(ズームと移動は matplotlib のツールバー)、描画が scatter / LineCollection / annotate で宣言的になった
- 難しくなった点: イベントループ(flush_events / start_event_loop)が見えにくい、Agg への黙った切り替えを自分で検出する必要がある、
  matplotlib の既定キー(l / k で対数軸など)が効いてしまう、テストでイベントを再現するのに monkeypatch が多い
- 無くなった機能: 負荷バー、マウスを重ねたときの詳細、ズームに応じたラベルの段階表示、縦横比の制限
- 検証: flake8・mypy --strict・pytest(870 passed)。Windows の実画面(TkAgg)で再生を確認。Linux / WSL では未確認(Linux では python3-tk が必要)

## matplotlib版を見た感想と、最小構成+matplotlib版

- 表示中のファイルを見るため、作業フォルダを `feature/matplotlib_view` に切り替えた(エージェントの worktree は未コミットの変更が無いことを確認して外した)
- impossible_dream(先頭のコメントと空行を除いた写し)で再生した
- ユーザーの指摘: 重ならないところも曲線になっている
  - 原因: `route` の判定は、レイアウト単位の `radius`(最も近いゾーン間隔の 0.3 倍)で行う。一方でゾーンは `scatter` で画面上の固定サイズに描き、
    軸も auto で引き伸ばされる。判定の大きさと描く大きさが別々になっている(pygame 版は同じピクセル半径で判定も描画もするので一致する)
  - 直し方の候補: A データ座標の円で描き、縦横比を固定する(推奨) / B 描いた大きさを判定に換算する / C 係数を小さくする
- ユーザー: 見た目のシンプルさは気に入った。これも反映して、最低限の版を見せてほしい
  - `feature/minimal_build` から `feature/minimal_matplotlib` を切り、最小限の matplotlib 表示(A の修正つき)を足す作業をサブエージェントに依頼した

## 最小構成+matplotlib版の結果(`feature/minimal_matplotlib`)

- コミット 6 件(ca9fba8〜d7384b7)。作者は noreply で、メッセージに個人情報なし(確認済み)
- `--graphical` フラグ1つを足した(ターミナル表示は常に出したまま、ウィンドウを足す)。フラグなしの出力は minimal_build と一致
- 曲線は案A で直した: ゾーンを判定と同じ半径でマップ単位のパッチとして描き、`set_aspect("equal")`
- 行数: graphical_view.py 308 行・geometry.py 225 行(matplotlib_view は 758 / 410)。droneflow/ 全体 5,153 行(minimal_build は 4,576)
- 削ったもの: PointGrid(巨大マップでは遅くなる)、弧どうしを重ねない工夫、軌跡の表示、ステップ・速度キー
- impossible_dream の画像で、ゾーンの間を通る線はまっすぐ、ゾーンの上を通る長い接続だけ曲がることを確認。密なマップではゾーン名が重なる
- 見てほしい判断: ウィンドウを閉じたら残りのターンを一瞬で進める(ターンログを完全に保つため)、名前・凡例・バッジを残した

- ユーザーの指示で、通過中の接続の色付けだけを戻した(`cf9b2ed`、+35 / −10 行、軌跡は戻さない)。pytest 659 件通過
  - matplotlib 版と同じ色(`#96a0b9`、通常色は `#555c6c`)なので、画像では違いがほとんど見えない

## 削った機能のうちレビューで役立つもの

- ユーザーの質問: 削った機能で、あるほうがレビューしやすいものはあるか
- 回答の要点: 戻すならステップ実行・要約行・BrokenPipe の特別扱い。次点は通過中の接続を目立たせること
- 調査記録: `docs/research/2026-10-23_minimal-build-review-features.md`

- ユーザーの指示で `feature/minimal_matplotlib` に2つ追加:
  - `8078d99` 要約行を戻した(develop と同じ `RunSummary`。subject_example・impossible_dream で develop と一致)
  - `8b8aedd` 通過中の接続を水色 `#00dcff`・太さ2倍にした(「通った場所」は、そのターンに通過中の接続と解釈した)
  - pytest 662 件通過。画像で水色の太線がはっきり見えることを確認

## 2026-10-24(日付変更)

### 提出物を簡易版に切り替える

- ユーザーの指示: 提出はこの簡易版(`feature/minimal_matplotlib`)にする。他はブランチに退避し、提出に必要な作業を行う
- pygame 版を退避: `archive/pygame_develop`(develop 6651766)、`archive/pygame_main`(main d00b383)
- develop に `feature/minimal_matplotlib` をマージした(4ca9fa6、--no-ff)。flake8・mypy(課題フラグ / --strict)・pytest 662 件は通過
- README の提出向けの手直し(試作の注記を消す、Linux の Tk の記載、課題 v2.0、AI の節からブランチ名を消す):
  README.ja.md は済み。README.md は一部の編集が権限確認で拒否され、途中(Tk と AI の節だけ反映)
- 残り: README.md の残り、コミット、main への反映(docs/・tests/ を除き、Makefile の test・pytest・[mypy-tests.*] を外す)、main での確認、push の確認

## 未決事項

- 試作の結果を見て、どちらか(または一部)を develop に取り込むかどうか
