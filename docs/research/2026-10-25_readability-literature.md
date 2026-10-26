# 可読性・コードの書き方に関する文献調査(命名・構造・関数の大きさ・抽象度・コメント)

- 日付: 2026-10-25
- 目的: 第三者から「命名や構造によってコードが理解しにくい」と指摘を受けたため、可読性について信頼できる資料が何を言っているかを調べ、
  実装担当がそのまま使える指針(G-1〜G-16)にまとめる。コードの箇所の洗い出しは実装担当が行う(この調査ではソースを読んでいない)。
- 方針(調整役の指示による): 各指針は「〜なら〜する」の形、コードで当てはまる箇所を探す手がかり、出典、その資料自身が述べている
  「適用しすぎの注意」だけを書く。指針の優先度付け・指針どうしの比較・推奨セットや実施順の判断はこの記録では行わない。
- 指針は調べ終えた順に、調整役(main)へ1件ずつ送付した。

## 調べた資料

| 資料 | 種類 | 入手方法 |
|---|---|---|
| PEP 8 – Style Guide for Python Code(https://peps.python.org/pep-0008/) | 一次資料 | Web で本文を取得 |
| PEP 257 – Docstring Conventions(https://peps.python.org/pep-0257/) | 一次資料 | Web で本文を取得 |
| PEP 3102 – Keyword-Only Arguments(https://peps.python.org/pep-3102/) | 一次資料 | 既知の内容(言語仕様) |
| Google Python Style Guide(https://google.github.io/styleguide/pyguide.html) | 一次資料 | Web で本文を取得 |
| The Hitchhiker's Guide to Python「Structuring Your Project」(https://docs.python-guide.org/writing/structure/) | 準一次資料 | Web で本文を取得 |
| John Ousterhout『A Philosophy of Software Design』(Yaknyam Press) | 書籍 | 章立ては書籍の知識と要約ノート(https://danlebrero.com/2021/02/24/philosophy-of-software-design-summary/)で確認 |
| Robert C. Martin『Clean Code』(Prentice Hall, 2008) | 書籍 | 書籍の知識(章・節の名前で参照) |
| Steve McConnell『Code Complete 2nd ed.』(Microsoft Press, 2004) | 書籍 | 書籍の知識(章・節の名前で参照) |
| Dustin Boswell & Trevor Foucher『The Art of Readable Code(リーダブルコード)』(O'Reilly, 2011) | 書籍 | 書籍の知識(章の名前で参照) |
| Felienne Hermans『The Programmer's Brain』(Manning, 2021)8章「How to get better at naming things」 | 書籍 | 目次のみ確認(https://www.oreilly.com/library/view/the-programmers-brain/9781617298677/Text/ch08.htm)。本文は未確認のため、指針の出典には使っていない |
| Hofmeister, Siegmund, Holt "Shorter identifier names take longer to comprehend", SANER 2017(https://www.se.cs.uni-saarland.de/publications/docs/HoSeHo17.pdf)。拡張版 Empirical Software Engineering 24(1), 2019 | 実証研究 | 要旨を確認 |
| Lawrie, Morrell, Feild, Binkley "What's in a name? A study of identifiers", ICPC 2006(https://ieeexplore.ieee.org/document/1631100) | 実証研究 | 要旨を確認 |
| Binkley, Davis, Lawrie, Morrell "To camelcase or under_score", ICPC 2009 / Sharif, Maletic "An Eye Tracking Study on camelCase and under_score Identifier Styles", ICPC 2010(https://ieeexplore.ieee.org/document/5521745) | 実証研究 | 要旨・紹介を確認 |
| Arnaoudova, Di Penta, Antoniol "Linguistic antipatterns: what they are and how developers perceive them", Empirical Software Engineering 21(1), 2016(DOI 10.1007/s10664-014-9350-8) | 実証研究 | 二次資料(紹介記事)で定義を確認。本文は未確認 |

注: 書籍は本文を Web で取得していない。章・節の名前と主張は書籍の知識に基づく。実証研究は要旨(と一部は紹介記事)での確認にとどまる。

## テーマ別の資料の主張

### 命名

- **PEP 8**: 公開 API の名前は「実装ではなく使われ方を反映する」。モジュールは短い小文字(アンダースコア可)、パッケージは短い小文字(アンダースコアは避ける)、
  クラスは CapWords、関数・変数は lower_with_under、定数は大文字。`l`・`O`・`I` を1文字名に使わない。
- **Google Python Style Guide 3.16**: 名前は説明的にし、説明的であることはスコープの広さに比例させる。「Avoid abbreviation」(単語の途中の文字を削らない)。
  1文字名はループの添字・`except` の `e`・`with` の `f` などに限る。`id_to_name_dict` のように型を名前に含めない。
- **Martin『Clean Code』2章**: 意図を表す名前、誤情報を避ける(Avoid Disinformation)、区別にならない語(Info, Data など)を避ける、1つの概念に1つの語(Pick One Word per Concept)、
  別の意味に同じ語を使わない(Don't Pun)。
- **Boswell & Foucher『リーダブルコード』2〜3章**: 具体的な語を選ぶ、tmp/retval などの汎用名を避ける(ただし本当に短命な値なら可)、単位や重要な属性を名前に付ける
  (誤解が深刻なバグになるときに限る)、範囲は first/last・begin/end、bool は is/has/can で否定形を避ける。
- **Ousterhout『A Philosophy of Software Design』14章**: 名前は正確で一貫しているべき。あいまいな名前は red flag。シンプルな名前を付けにくいのは設計がきれいでない兆し。
- **McConnell『Code Complete』11章**: 変数名の付け方、略語を使う場合のガイドライン。
- **実証研究**:
  - Hofmeister ら(SANER 2017): プロの開発者72人。単語の識別子は、文字・略語の識別子より欠陥の発見が平均約19%速かった。文字と略語の間には有意差なし。
  - Lawrie ら(ICPC 2006): 100人以上。全単語の識別子が最もよく理解された。ただし全単語と略語の差は多くの場合有意でなかった。
  - Binkley ら(ICPC 2009)/Sharif & Maletic(ICPC 2010): camelCase と under_score で正確さに差はなく、under_score の方が速く認識された(2010)。
    Python の PEP 8 の lower_with_under をそのまま使えばよい根拠の一つ。
  - Arnaoudova ら(EMSE 2016): 名前が約束する振る舞いと実際の振る舞いの食い違いを「言語的アンチパターン」と定義(get が単に返す以上のことをする、
    is が bool 以外を返す など)。開発者の多くがこれを悪いものと評価した。

### 構造・モジュール分割

- **PEP 8**: 迷ったら非公開(`_`)にする。文書化されていないインターフェースは内部とみなす。`__all__` で公開 API を宣言できる。
- **PEP 257**: モジュール・パッケージの docstring は、公開するクラス・関数・サブモジュールを1行ずつ列挙する。
- **Google Python Style Guide 2.2・2.3**: import はパッケージとモジュールに対して行い、フルパッケージ名を使う。
- **Hitchhiker's Guide「Structuring Your Project」**: モジュール名は短く小文字。アンダースコアで名前空間を作らずサブモジュールを使う。
  循環依存、隠れた結合、グローバル状態、`__init__.py` に多くのコードを置くことを悪い構造の兆しとして挙げる。`__init__.py` を空にしておくのは普通でよいこと。
  構造のない分割(spaghetti code)と、構造のない小片の大量生成(ravioli code)の両方を失敗として挙げる。
- **Ousterhout 4・5・7章**: よいモジュールは「深い」(単純なインターフェースの裏に多くの機能)。小さいクラスを大量に作る classitis への注意。
  同じ設計判断が複数のモジュールに現れるのは情報の漏れ。処理の順番でモジュールを分ける temporal decomposition は漏れを起こしやすい。
  pass-through method / pass-through variable、隣り合う層が同じような抽象を持つことは red flag。クラスを少し大きくする方が情報の隠蔽がよくなることが多い。

### 関数・クラスの大きさと責務

- **Google Python Style Guide 3.18**: 小さく焦点の定まった関数を好む。約40行を超えたら構造を損なわずに分けられるか考える。厳密な上限はなく、長い関数が適切なこともある。
- **Martin『Clean Code』3章・10章**: 関数は小さく、1つのことをする。フラグ引数は複数のことをする宣言。クラスは小さく、単一責任。
  クラスの説明は「if」「and」「or」「but」を使わずに約25語で書けるべき。
- **McConnell『Code Complete』7章**: ルーチンを作る理由(複雑さを減らす、中間的な抽象を導入する)。7.4 で、まとまりのあるルーチンなら100〜200行程度でも
  欠陥率や理解しやすさが悪くならないという研究を挙げ、行数の制限を目的にしないよう述べる。
- **Ousterhout 4・9章**: 分けた結果、片方の実装を理解するのにもう片方の実装を読む必要があるなら、分けるべきでない。

### 抽象度・流れの追いやすさ

- **Martin『Clean Code』3章**: 1つの関数の中の抽象度をそろえる(One Level of Abstraction per Function)。上から下へ一段ずつ抽象度が下がるように読める(Stepdown Rule)。
  5章: 関係の深い概念は縦に近く置き、呼ぶ関数を呼ばれる関数の上に置く。
- **Boswell & Foucher『リーダブルコード』**: 4章 意味のある順番を一貫して使う。7章 入れ子を浅くし早期 return を使う。8章 説明変数・要約変数で巨大な式を分ける。
  9章 変数のスコープを縮め、一度だけ書き込む変数を好み、役に立たない一時変数は消す。10章 高レベルの目的と関係ない部分問題を切り出す
  (ただし切り出しすぎて小さな関数が散ると逆に読みにくい)。
- **McConnell『Code Complete』10章**: 変数の参照の間隔(span)と生存期間(live time)を短くし、最初に使う近くで初期化し、1つの変数を1つの目的にだけ使う。12章 マジックナンバーを避ける。
- **Martin『Clean Code』17章**: G16 Obscured Intent、G25 マジックナンバーを名前付き定数に(ただし自明な数、例えば円周の式の 2 まで定数にする必要はない)。

### コメントと docstring

- **PEP 8**: コードと矛盾するコメントはないより悪い。コードを変えたらコメントも更新する。自明なことを言うインラインコメントは不要で邪魔。
- **PEP 257**: 1行目は効果を命令形で書く(「Do this」「Return that」)。シグネチャを繰り返すだけの docstring にしない。
  関数の docstring は振る舞い、引数、戻り値、副作用、送出する例外、呼び出しの制約を書く。クラスは振る舞いと公開メソッド・インスタンス変数を書き、コンストラクタは `__init__` に書く。
- **Google Python Style Guide 3.8**: 公開 API・大きい関数・自明でないロジックの関数には docstring を必須とする。docstring はコードを読まずに呼び出せるだけの情報を持つ。
  クラスの docstring は「インスタンスが何を表すか」の1行要約で始める。コメントでは「never describe the code」。
- **Ousterhout 12〜16章**: 「よいコードは自分自身を説明する」は神話。コメントはコードから明らかでないことを書き、精度か直感を足す。インターフェースのコメントと実装のコメントを分ける。
  コードの繰り返しになっているコメントは red flag。コメントを先に書くと設計の問題に早く気付ける。
- **Boswell & Foucher『リーダブルコード』5〜6章**: コードからすぐわかることは書かない。ひどい名前をコメントで補うより名前を直す。自分の考え・欠陥・定数の理由を書く。

## 指針(G-1〜G-16)

各項目: 指針 / 手がかり(コードで当てはまる箇所を探す方法) / 出典 / 資料自身が述べる適用しすぎの注意。番号は送付した順であり、優先度ではない。

### G-1 名前と中身(型・振る舞い)の食い違い

- 指針: 名前が中身と食い違うなら、名前を中身に合わせて直す。is_/has_/can_ なのに bool 以外を返す、get_ や名詞の property なのに重い計算・状態の変更・新しいオブジェクトの生成をする、
  単数形の名前がコレクションを持つ(またはその逆)、set_ なのに値を返す、など。基本は名前を変え、振る舞いは変えない。
- 手がかり: `def (is|has|can|should)_` の戻り値の型注釈が `bool` か。`def get_` と `@property` の本体に代入・append・状態変更・探索のループがないか。名前の単数/複数と型注釈(`list`/`dict`/`set`)が合うか。
- 出典: Arnaoudova ら(EMSE 2016)、Martin『Clean Code』2章「Avoid Disinformation」、Ousterhout 14章、PEP 8(使われ方を反映する名前)。
- 資料自身の注意: 名前を変えたら、関係するコメント・docstring も直す(PEP 8: コードと矛盾するコメントはないより悪い)。Ousterhout 17章は既存の慣習を「改善」するのは多くの場合割に合わないとする。

### G-2 1つの概念に1つの語

- 指針: 同じ概念に別々の語、または別々の概念に同じ語を使っているなら、1つの概念に1つの語にそろえる。
- 手がかり: 主要な型ごとに、その型の注釈がついた変数・引数・属性の名前を grep で並べ、何種類あるかを見る。同じ動作のメソッドの動詞(get/fetch/find/lookup、build/make/create)がクラス間でばらついていないか。
- 出典: Martin『Clean Code』2章「Pick One Word per Concept」「Don't Pun」、Ousterhout 14章・17章、PEP 8(プロジェクト内・モジュール内の一貫性)。
- 資料自身の注意: 特になし。

### G-3 広いスコープの略語・1文字名

- 指針: 広いスコープ(引数・属性・モジュール変数・数行を超えて使う変数)に略語や1文字の名前があるなら、全単語の名前にする。名前の具体さはスコープの広さに比例させる。
- 手がかり: 引数名・属性名・モジュールレベルの名前で3文字以下のもの、母音を抜いた形のもの。1文字名は定義から最後の使用までの行数。
- 出典: Hofmeister ら(SANER 2017)、Lawrie ら(ICPC 2006)、Google Python Style Guide 3.16、McConnell『Code Complete』11章。
- 資料自身の注意: Google 3.16 はループの添字、`except` の `e`、`with` の `f` などの1文字名を認め、説明的であることはスコープに比例させるとする。Lawrie らは全単語と略語の差は多くの場合有意でないとしている。

### G-4 汎用的な語だけの名前

- 指針: 名前が汎用的な語(data, info, result, value, tmp, obj, item, manager, handler, process, handle, do_)だけでできているなら、何の何か・何をするかを表す具体的な語にする。
- 手がかり: `\b(data|info|result|value|tmp|temp|obj|item)\b` の grep、`Manager|Handler|Processor|Helper|Util` で終わるクラス名、`def (process|handle|do|run)_?` で始まる関数。
- 出典: Boswell & Foucher『リーダブルコード』2章、Ousterhout 14章、Martin『Clean Code』2章「Use Intention-Revealing Names」「Avoid Noise Words」。
- 資料自身の注意: Boswell 2章は、スコープが数行で本当に一時的な値なら tmp のような汎用名も許容する(汎用名は理由があるときだけ使う)。

### G-5 モジュール/パッケージの名前と中身

- 指針: モジュール/パッケージの名前から中身が予想できない(名前と中身がずれている、名前で表せない別の役割が同居している)なら、中身を名前に合うモジュールへ移すか、名前を中身に合わせる。
- 手がかり: 各モジュールの docstring の1行要約が名前と同じことを言うか。PEP 257 の形で公開する名前を列挙して、1つの名前でくくれるか。`utils`/`helpers`/`common`/`misc` のような名前があるか。
- 出典: PEP 8「Package and Module Names」、Hitchhiker's Guide「Structuring Your Project」、PEP 257、Google Python Style Guide 2.2・2.3。
- 資料自身の注意: Hitchhiker's Guide は、構造のない小片を大量に作る ravioli code を失敗として挙げる。循環 import を関数内 import のような壊れやすい対処で避ける形になるなら、構成の方を見直すべきとする。

### G-6 1つの関数の中の抽象度をそろえる

- 指針: 1つの関数に、高いレベルの手順と低いレベルの細部(添字計算、辞書の出し入れ、文字列の組み立て)が混ざっているなら、低いレベルの部分を、何をするかを表す名前の関数に切り出し、元の関数を同じ抽象度の呼び出しの並びにする。
- 手がかり: メソッド呼び出しの並びの間に、ループ・内包表記・添字操作のかたまりが挟まる関数。かたまりの前に見出し的なコメント(「# 〜を求める」)がある箇所(そのコメントが関数名の候補になる)。
- 出典: Martin『Clean Code』3章「One Level of Abstraction per Function」「The Stepdown Rule」、Boswell & Foucher『リーダブルコード』10章、McConnell『Code Complete』7章。
- 資料自身の注意: Boswell 10章は、切り出しすぎて小さな関数が散ると読み手が飛び回ることになり逆に読みにくいとする。Ousterhout 9章は、片方の実装を理解するのにもう片方の実装を読む必要があるなら分けるべきでないとする。

### G-7 関数の長さと入れ子の深さ

- 指針: 関数が約40行を超える、または入れ子が深いなら、構造を損なわずに分けられるか、早期 return / continue で入れ子を浅くできるかを検討する。
- 手がかり: `ast` で関数ごとの行数(docstring を除く)と最大の入れ子の深さを数える。else の中に本体の大部分があるもの、ガード節にできる条件が先頭にあるもの。
- 出典: Google Python Style Guide 3.18、Boswell & Foucher『リーダブルコード』7章、Martin『Clean Code』3章「Small!」、McConnell『Code Complete』7.4。
- 資料自身の注意: Google 3.18 は厳密な上限を置かず、長い関数が適切なこともあるとする。McConnell 7.4 は、まとまりのあるルーチンなら100〜200行程度でも問題ないという研究を挙げ、行数の制限を目的にしないよう述べる。

### G-8 浅いモジュールと pass-through

- 指針: メソッドが引数を別のオブジェクトの同じようなメソッドにそのまま渡すだけ、またはクラス・モジュールのインターフェースが中身と同じくらい複雑なら、その層が何を隠しているかを確かめ、
  何も隠していなければ呼び出し側から直接使う形にするか、隠すべき知識をその層に集める。
- 手がかり: 本体が `return self._x.same_name(...)` の1行だけのメソッド。自分では使わず下へ渡すだけの引数が何段も通るもの。同じ設計上の決まり(数え方、形式の細部)を知っているモジュールが複数あるもの。
- 出典: Ousterhout 4章「Modules Should Be Deep」(classitis)、5章「Information Hiding (and Leakage)」(temporal decomposition)、7章「Different Layer, Different Abstraction」。
- 資料自身の注意: Ousterhout 7章は、同じシグネチャでも複数の実装に振り分ける dispatcher や、同じインターフェースの複数の実装(デコレータ等)は問題でないとする。5章は、クラスを少し大きくする方が情報の隠蔽がよくなることが多いとする。

### G-9 説明変数と名前付き定数

- 指針: 条件式や計算式が長く、何を判定・計算しているかが一目でわからないなら、途中の値に名前を付けた変数に分ける。意味のある数値・文字列の直書きが複数か所にあるなら、名前の付いた定数にする。
- 手がかり: `and`/`or` が3つ以上つながる if、比較と算術が混ざる式、同じ式が複数か所にあるもの。0/1/-1 以外の数値リテラル、同じ文字列リテラルが複数ファイルにあるもの。
- 出典: Boswell & Foucher『リーダブルコード』8章、Martin『Clean Code』17章 G16・G25、PEP 8「Constants」、McConnell『Code Complete』12章。
- 資料自身の注意: Boswell 9章は、式を分けも明確にもせず意味を足さない一時変数は消すべきとする。Martin G25 は、自明な数(円周の式の 2 など)まで定数にする必要はないとする。

### G-10 コメントは「なぜ」を書き、コードと食い違わせない

- 指針: コメントや docstring の説明文がコードの言い換えだけなら、コードから読み取れないこと(理由、前提・不変条件、単位や範囲、選ばなかった方法とその理由)に書き換えるか削る。コードと食い違うコメントは必ず直す。
- 手がかり: 直下の1行と同じ内容のコメント。関数名をそのまま文にしただけの docstring 要約。改名・仕様変更後に古い語や古い挙動を説明しているコメント。
- 出典: PEP 8「Comments」、Google Python Style Guide 3.8.5、Ousterhout 13章、Boswell & Foucher『リーダブルコード』5章。
- 資料自身の注意: Ousterhout 12章は「よいコードは自分自身を説明するのでコメントは要らない」は神話とし、インターフェースの説明は書くべきとする。Google 3.8.3 も公開 API・大きい関数・自明でないロジックには docstring を必須とする。

### G-11 docstring の1行目で責務を言えるか

- 指針: クラスの docstring の1行目で「インスタンスが何を表すか」を一文で言えない、または関数の1行目の要約に複数の仕事が並ぶなら、その名前・責務を見直す(1つの物・1つの効果として言える単位にする、または名前を要約に合わせる)。
- 手がかり: クラス docstring の1行目に and/および/かつ、または「〜を管理する」「〜を扱う」のようなぼかした動詞しかないもの。関数 docstring の1行目が命令形の効果になっていないもの、シグネチャの言い換えだけのもの。
- 出典: Google Python Style Guide 3.8.4、PEP 257、Ousterhout 14章・15章、Martin『Clean Code』10章「Classes Should Be Small」。
- 資料自身の注意: Ousterhout 4章は、細かく分けすぎて小さなクラスを大量に作る classitis に注意する。

### G-12 bool のフラグ引数

- 指針: 関数が bool の引数を受け取り、その値で別々の処理に分かれるなら、名前で区別できる別の関数にするか、少なくともキーワード専用引数(`def f(..., *, flag: bool)`)にして呼び出し側で意味を読めるようにする。
- 手がかり: 型注釈が `bool` の引数を持ち、本体の最上位が `if flag:` で大きく分かれる関数。呼び出し側の位置指定の `True`/`False`。
- 出典: Martin『Clean Code』3章「Flag Arguments」、PEP 3102(キーワード専用引数)、Boswell & Foucher『リーダブルコード』2章(名前付き引数で呼び出しの意味を明らかにする)。
- 資料自身の注意: 特になし。

### G-13 公開/非公開を名前で示す

- 指針: 外から使われない関数・メソッド・属性・定数に `_` が付いていない(または外から使われるものに `_` が付いている)なら、実際の使われ方に合わせて `_` の有無をそろえる。
- 手がかり: `_` なしの名前を定義モジュール以外で grep して、使われていないもの。`_` 付きの名前を他モジュールから参照しているもの(テストを除く)。`__init__.py` の再エクスポートと実際に外から使う名前が合うか。
- 出典: PEP 8「Designing for Inheritance」「Public and Internal Interfaces」、Ousterhout 5章。
- 資料自身の注意: PEP 8 は、公開 API を変えると後方互換性の問題が出るため、公開か非公開かは慎重に決めるべきとする。

### G-14 型は名前から外し、型で表せない情報は名前に入れる

- 指針: 変数名に型の名前が重ねてあるなら、型は型注釈に任せて名前から外す。型注釈で表せない重要な情報(単位、ターン番号か経過ターン数か、0始まりか1始まりか、検証済みか)があるなら名前に入れる。
- 手がかり: `_list`、`_dict`、`_set`、`_str`、`_int`、`_tuple` で終わる名前。何を数えているか・単位が名前からわからない int/float の変数。
- 出典: Google Python Style Guide 3.16.1、Boswell & Foucher『リーダブルコード』2章「Attaching Extra Information to a Name」、3章「Names That Can't Be Misconstrued」。
- 資料自身の注意: Boswell 2章は、情報を付け足すのは誤解が深刻なバグになるときに限り、すべての変数に付けるべきではないとする。

### G-15 変数の定義と使用を近づけ、1変数1目的にする

- 指針: 変数の定義から使用までが遠い、冒頭でまとめて定義した変数が後半でしか使われないなら、最初に使う直前で定義する。中間の値を何度も書き換える変数は、一度だけ代入する別の名前の変数に分ける。
- 手がかり: 先頭で初期化され数十行後で初めて読まれる変数。別の意味の値を再代入している変数。1つのメソッドの中でしか使われないインスタンス属性やモジュール変数。
- 出典: McConnell『Code Complete』10章、Boswell & Foucher『リーダブルコード』9章、Hitchhiker's Guide「Structuring Your Project」(書き換えられるグローバル状態は推論とデバッグを難しくする)。
- 資料自身の注意: 特になし。

### G-16 ファイル内の並び順をそろえる

- 指針: ファイル内の関数・メソッドの並び順に決まりがないなら、呼ぶ側を上・呼ばれる側をその下に置き、関係の深いものを近くにまとめる並べ方をファイル内・プロジェクト内で一つにそろえる。
- 手がかり: 公開メソッドと、その中で呼ぶ `_` 付き補助メソッドが大きく離れているもの。同じパッケージ内のクラス間で `__init__`・公開メソッド・property・非公開メソッドの順がばらばらなもの。
- 出典: Martin『Clean Code』5章「Vertical Distance」「Vertical Ordering」、Boswell & Foucher『リーダブルコード』4章、PEP 8「A Foolish Consistency is the Hobgoblin of Little Minds」。
- 資料自身の注意: PEP 8 は同じ節で、ガイドを当てはめるとかえって読みにくくなる場合や、周りのコードとの一貫性を保つ場合は従わなくてよいとする。

## 送付の記録

- G-1〜G-16 を main に1件ずつ送付済み。
- G-1〜G-3 は当初「優先度」と資料に基づかない注意書きを付けて送ったが、方針変更を受けて G-4 の送付時に撤回を伝えた(この記録の G-1〜G-3 は撤回後の内容)。
- G-12 の出典に誤って「Google Python Style Guide 3.19 系」を含めたため、G-13 の送付時に訂正した。G-15 の出典の誤記(「PEP 8「Comments」とは別に」)は G-16 の送付時に訂正した。
