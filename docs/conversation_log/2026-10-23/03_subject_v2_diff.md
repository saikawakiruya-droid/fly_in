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

## 2026-10-26(日付変更)

### 依頼

PDF は残して、ほかは main まで反映する。

### 作業

- `test/subject_v2_optimum` を develop にマージした(7288faa)。develop で pytest 662 件成功、flake8・mypy(課題のフラグ)問題なし。
  ブランチは削除。使っていたワークツリーは登録が外れていたので、ディレクトリを削除した。
- この会話の docs(調査記録・決定記録・このログ)は、別のセッションで develop にコミット済みだった(53fc3a2)。
- main: tests は main に含めないので、テストの変更は反映するものが無い。develop に入っていて main に未反映だった
  読みやすさの改善(`droneflow/` の変更)を、`droneflow/` と `fly_in.py` を develop からそのまま取って反映した(d2d54cd)。
  main と develop の差(docs・tests を除く)は、決まった tests 関連の行(Makefile・README・requirements.txt・setup.cfg)と
  `maps.tar.gz` だけであることを確認した。main で flake8・mypy(課題のフラグと --strict)問題なし、課題の例は5ターン。
- `fly_in.pdf`(v2.0)はそのまま残した(`.gitignore` の対象)。
- push はしていない。

## 2026-10-27(日付変更)

- ユーザーの指示で main と develop を push した(main d2d54cd、develop 0570bdf)。push 前に、送るコミットのメッセージと差分に
  個人情報・セッションURLが無いことを確認した(作業場所の `D:\WorkSpaceclaude_code\...` のパスが1か所あるが、ユーザー名を含まず、
  同じ形のパスは origin にすでにある)。

## 未決事項

- なし。

## 2026-11-10(日付変更)

- 依頼: PDF にファイル構造についての記述があるらしいので見てほしい。
- 結果: 記述は X 章の "Place all your files at the root of your repository."(v1.6 からある文)と、README・Makefile・.gitignore・
  テスト(提出しない)の規定だけ。ファイル名やディレクトリ構成の指定は無い。今の main は満たすと判断した。
- 作成: `docs/research/2026-11-10_subject-file-structure.md`
- ユーザーの判断: X 章の文は「全ソースファイルはリポジトリ直下」が条件と読む。

### 依頼: 委譲関係をもとにファイル名を変えて、わかりやすく並ぶように。表示はそれぞれ単一ファイルにして、オプションを付けたら使う

- 案(`_tmp/flat_rename_plan.md`)を作り、命名の方式(持ち主の名前を先頭に付ける)をユーザーが選んだ。
- 外付けSSD(D:)がつながっていなかったので、ワークツリーは `.claude/worktrees/flat_layout` に作った。
- `feature/flat_layout` に実装(c50dd14 コードとテスト、494c952 README)。
  - `droneflow/` をやめて全 `.py` を直下へ。名前は持ち主の名前で始める(対応表は README の「Code structure」)。
  - `terminal_view.py` に色名の表を取り込み、`matplotlib_window.py` にウィンドウ・シーン・平面の計算を委譲の順でまとめた。
    matplotlib 側は matplotlib の色名を使う。
  - `--terminal-view` を追加。表示はオプションを付けたときだけ使う。テストを合わせ、AC07・AC08・AA15 を追加。
  - テスト 666 件成功、flake8・mypy(課題のフラグと --strict)問題なし。`.venv` に matplotlib が入っていなかったので
    `requirements.txt` から入れ直した(入っていないと mypy が matplotlib の型を Any とみなしてエラーになる。develop でも同じ)。
- 決定記録: `docs/decisions.md` 2026-11-10。

### 依頼: 移動しているように見えない・キャッシュを消す、マージして不要なものを削除

- メインのチェックアウト(develop)にはブランチの変更がまだ入っていなかったため、移動していないように見えていた。
- `feature/flat_layout` を develop にマージした(7a0bc1b)。develop でテスト 666 件成功、flake8・mypy --strict 問題なし、課題の例は5ターン。
- 削除したもの: キャッシュだけが残った `droneflow/`、`__pycache__`・`.mypy_cache`・`.pytest_cache`(`.venv` の外)、
  空になった `tests/interchange/`・`tests/visualization/graphical/`、ワークツリー `.claude/worktrees/flat_layout`、
  ブランチ `feature/flat_layout`、`_tmp/flat_rename_plan.md`(内容は決定記録と README に移した)。

### 依頼: ファイルが多すぎるので整理の提案を

- 案A(持ち主ごとに1ファイル、11ファイル)と案B(大きい map_parser と scheduler だけ2つに分ける、13ファイル)を出し、
  ユーザーは案Bを選んだ。cli は `fly_in.py` に入れると import が循環するので `app.py` に入れる。
- ブランチ `feature/fewer_modules` を develop から作ったところで止めた(まだ変更なし)。main への反映も、整理の後にやり直す。

### 依頼: ほかの人の課題で決まった変更点 — 同じ接続の禁止、`nb_drones` はコメント行を除いた1行目

- 重複した接続はすでに拒否していたので、残っていた `a-a` を拒否するルールを追加した。`nb_drones` はコメントと空行を
  読み飛ばした最初の行にした。ブランチ `fix/map_header_rules`(ca3f932・1a6c649)。決定記録: `docs/decisions.md` 2026-11-10。

## 未決事項

- `fix/map_header_rules` を develop にマージするか(ユーザーの許可待ち)。
- そのあと案B の整理(`feature/fewer_modules`)を進め、main に反映して push する。
- `.claude/worktrees/main_sync` のフォルダ(使用中で削除できなかった)を片付ける。
