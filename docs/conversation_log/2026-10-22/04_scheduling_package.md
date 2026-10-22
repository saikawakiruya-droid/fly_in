# 2026-10-22 会話ログ: プログラムの構成と `simulation/scheduling/` への整理

- 開始: 2026-10-22 17:30 頃

## プログラムの構成(親子関係)

- 依頼: プログラムの構成を、親子関係がわかるように簡単に書く。
- 回答: `fly_in.py` → `Application.run()` の下に ①マップ読み込み(parsing / WorldFile) ②経路(Pathfinder, DistanceMap)
  ③シミュレーション(SimulationEngine → TurnResolver・SimulationState・Scheduler → 部品) ④出力(ObserverGroup に printer・
  RunRecorder・表示)を並べ、models/ は共通の土台として別に書いた。

## ファイル構成への反映

- 依頼: この図をファイル構成に反映できるか。
- 回答: 今の構成はすでに①〜④とほぼ同じ。違いは (a) Scheduler の子が `simulation/` にエンジン側と並んでいる、(b) `interchange/` に①と④が同居、の2点。
  案 A(Scheduler の子だけ `simulation/scheduling/` に)、B(interchange を分ける。見送りを推奨)、C(図をそのまま再現。見送りを推奨)を出した。
- 決定: ユーザーが A を選択(「ほかのセッションの作業が終わったら A をして」)。
- 作業: 別セッション(`test/drop_windows_support`、マージ許可待ち)の作業ツリーに触れないよう、別の worktree で
  `feature/scheduling_package`(develop から)を作った。8モジュールと9テストファイルを `git mv`、import を書き換え、
  README 両版のコード構成と `tests/README.md` のパスを更新。決定は `docs/decisions.md`。
- 検証: Windows で flake8・mypy・pytest 884件成功。WSL で make lint 成功、make test は VG08(グラフィカル表示)だけが
  ときどき失敗。develop でも同じく失敗するので移動とは無関係(`docs/bugs.md` に記録)。
- 未決: `feature/scheduling_package` の develop へのマージ(ユーザーの許可待ち)。`test/drop_windows_support` と両方が
  `docs/decisions.md` の末尾に追記しているので、後からマージする方で衝突を解く必要がある。VG08 の不安定さの調査。
