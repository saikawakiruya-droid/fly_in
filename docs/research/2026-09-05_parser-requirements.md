# 調査記録: 入力部(パーサ)の課題要件抜き出し

- 日付: 2026-09-05
- 依頼内容: 「入力部を作成する」にあたり、関係する課題要件を抜き出す
- 対象ソース: `fly_in.pdf` 章VI(Let the drone fly)、章VII.4(Parser Constraints)、章III(Common Instructions)、章V(Constraints)

## 入力フォーマットの構造(章VI)

- 1行目は必ず `nb_drones: <正の整数>`
- ゾーン定義行(1行1ゾーン):
  - `start_hub: <name> <x> <y> [metadata]` — 開始ゾーン
  - `end_hub: <name> <x> <y> [metadata]` — 終了ゾーン
  - `hub: <name> <x> <y> [metadata]` — 通常ゾーン
- 接続行: `connection: <name1>-<name2> [metadata]`(双方向)
- コメント: `#` から始まる行は無視する
- メタデータ(`[...]`内、省略可・順不同):
  - `zone=<type>`(既定値 normal)
  - `color=<value>`(既定値 none。任意の1語文字列、色名の固定リストなし)
  - `max_drones=<number>`(既定値 1)
  - 接続側のみ: `max_link_capacity=<number>`(既定値 1)
- ゾーンタイプと移動コスト:
  - normal: 1ターン(既定)
  - blocked: 侵入不可(通過する経路は無効)
  - restricted: 2ターン
  - priority: 1ターン(経路探索で優先されるべき。パーサ側は値の保持のみ)
- 座標は常に整数

### 入力例(仕様書記載)

```
nb_drones: 5

start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: roof2 6 2 [zone=normal color=blue]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
hub: tunnelB 7 4 [zone=normal color=red]
hub: obstacleX 5 5 [zone=blocked color=gray]
connection: hub-roof1
connection: hub-corridorA
connection: roof1-roof2
connection: roof2-goal
connection: corridorA-tunnelB [max_link_capacity=2]
connection: tunnelB-goal
```

## パーサ制約 = バリデーション要件(章VII.4)

- `nb_drones:` は正の整数。任意の台数に対応できること。
- `start_hub:` と `end_hub:` はそれぞれちょうど1つ存在すること。
- 各ゾーンは名前が一意、座標は整数であること。
- ゾーン名に使える文字はダッシュ(`-`)とスペース以外(ダッシュは接続構文の区切り文字と衝突するため禁止)。
- `connection:` は既に定義済みのゾーンのみ参照可能 → ゾーン定義が接続定義より前に来る前提の処理が必要。
- 重複接続は不可: `a-b` と `b-a` は同一接続とみなしてエラー。
- メタデータブロック(`[...]`)は構文的に正しいこと(不正な形式はエラー)。
- ゾーンタイプは `normal` / `blocked` / `restricted` / `priority` の4種のみ。それ以外はパースエラー。
- 容量値(`max_drones`, `max_link_capacity`)は正の整数であること。
- `max_drones` は `start_hub` / `end_hub` に指定されていても無視する(エラーにしない = 無制限)。
- 上記以外の不正(構文エラー等)は、行番号と原因を明示したエラーメッセージでプログラムを停止させること。
- (推奨)提供マップ以外に、エッジケース検証用の自作マップを作ること。

## 共通ルールのうち入力部に直接効いてくるもの(章III・章V)

- 例外処理: 不正入力で未処理例外によりクラッシュしてはいけない(評価上「非機能」と見なされる)→ try-except で捕捉し、上記のエラーメッセージ形式で終了させる。
- リソース管理: ファイル読み込みは context manager(`with open(...) as f:`)を使う。
- 型安全: 全関数・メソッドに型ヒント、mypyでエラーなし。
- docstring: PEP 257準拠でクラス・関数に付与。
- 完全にオブジェクト指向(章V): パーサは関数の羅列ではなく、クラスとして設計すること。
- グラフ系ライブラリ禁止(章V): パーサが構築するネットワーク構造自体も自前実装であること(networkx等禁止)。

## パーサが後段に渡すべき情報(下流ステージの要求から逆算)

- 各ゾーン: name, x, y, zone_type, color, max_drones(start/endは実質無制限扱い)
- 各接続: 両端のゾーン名, max_link_capacity
- ドローン数(`nb_drones`)
- start/endゾーンの識別(一意)
