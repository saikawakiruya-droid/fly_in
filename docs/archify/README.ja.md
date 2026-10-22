# archify 図の置き場

archify で作った図のうち、残すものを置く場所。フォルダ単位(構造)と機能単位(実行時の動き)の2種類がある。
`docs/` 配下なので `develop` にだけコミットし、`main`(提出物)には含めない。

## 構成

```
docs/archify/
└── <図の名前>/            # folder-<名前> または feature-<名前>
    ├── candidate.json      # 図の元データ(正本)
    └── <図の名前>.html     # 生成された図(ブラウザで開く)
```

- 1つの図に1つのフォルダ。図を更新するときは同じフォルダで上書きし、過去の版は git の履歴で追う。
- どのコードの時点を描いたかは `candidate.json` の `meta.repository.revision`(コミット)で分かる。
- 検証の記録(`*.finalize*.json`、`*.browser-check.json`、`*.delivery.json`、`review-*/`)は `.gitignore` で除外する。

## 図の一覧

フォルダ単位(`folder-*`: どこに何があるか):

| フォルダ | 種類 | 内容 |
|---|---|---|
| `folder-tree` | tree | リポジトリのフォルダとファイルの一覧 |
| `folder-overview` | architecture | どのフォルダがどのフォルダを import しているか |
| `folder-top-level` | class | `app.py`・`cli.py`・`errors.py`(例外の親子関係) |
| `folder-models` | class | `models/` |
| `folder-parsing` | class | `parsing/` |
| `folder-interchange` | class | `interchange/` |
| `folder-pathfinding` | class | `pathfinding/` |
| `folder-simulation` | class | `simulation/`(エンジン側) |
| `folder-scheduling` | class | `simulation/scheduling/` |
| `folder-output` | class | `output/` |
| `folder-visualization` | class | `visualization/` |

機能単位(`feature-*`: 動かしたときに何が起きるか):

| フォルダ | 種類 | 内容 |
|---|---|---|
| `feature-run` | workflow | `fly_in.py` から終了コードまで(オプションによる分岐を含む) |
| `feature-parse` | sequence | マップファイルを読んで World を作る |
| `feature-pathfinding` | workflow | 距離と次の一手の計算 |
| `feature-turn` | sequence | 1ターン: 決める → 確かめて適用 → 通知 |
| `feature-decide` | workflow | Scheduler が1ターンの手を決める手順 |
| `feature-drone` | lifecycle | ドローン1機の状態の移り変わり |
| `feature-output` | dataflow | 出力の種類ごとの行き先 |

## 作り方

1. 会話中の下書きは、これまでどおり `_tmp/` で作る。
2. 残すと決めた図だけをここへ移す(昇格)。`candidate.json` の `meta.output` を新しい場所
   (`docs/archify/<図の名前>/<図の名前>.html`)に書き換え、archify の `finalize` で HTML を作り直す。
3. 昇格した下書きは `_tmp/` から消す(昇格とセットで行う)。
