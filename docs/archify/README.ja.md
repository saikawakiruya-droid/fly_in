# archify 図の置き場

archify で作った図(全体像・Stage ごとの構造図など)のうち、残すものを置く場所。
`docs/` 配下なので `develop` にだけコミットし、`main`(提出物)には含めない。

## 構成

```
docs/archify/
└── <図の名前>/            # 例: overview, stage1-models, stage5-scheduler
    ├── candidate.json      # 図の元データ(正本)
    └── <図の名前>.html     # 生成された図(ブラウザで開く)
```

- 1つの図に1つのフォルダ。図を更新するときは同じフォルダで上書きし、過去の版は git の履歴で追う。
- どのコードの時点を描いたかは `candidate.json` の `meta.repository.revision`(コミット)で分かる。
- 検証の記録(`*.finalize*.json`、`*.browser-check.json`、`*.delivery.json`、`review-*/`)は `.gitignore` で除外する。

## 作り方

1. 会話中の下書きは、これまでどおり `_tmp/` で作る。
2. 残すと決めた図だけをここへ移す(昇格)。`candidate.json` の `meta.output` を新しい場所
   (`docs/archify/<図の名前>/<図の名前>.html`)に書き換え、archify の `finalize` で HTML を作り直す。
3. 昇格した下書きは `_tmp/` から消す(昇格とセットで行う)。
