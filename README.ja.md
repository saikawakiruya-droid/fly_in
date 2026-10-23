*This project has been created as part of the 42 curriculum by naarai.*

# Fly-in

(このファイルは `README.md`(英語版)の日本語版です。課題の要件により、正式な README は英語版です。)

## Description

Fly-in は、Python で書いたドローン群のルーティングシミュレーションです。マップファイルには、
ゾーン(ノード)と、それらを結ぶ双方向のコネクション(エッジ)からなるネットワークが書かれています。
すべてのドローンはスタートゾーンから出発し、課題の移動ルールを守りながら、全機を**できるだけ少ない
シミュレーションターン数で**エンドゾーンへ運ぶことが目標です。

- ゾーンに同時にいられるドローンは `max_drones` 機まで(既定は 1)。スタートとエンドは無制限。
- コネクションを同じターンに通れるドローンは `max_link_capacity` 機まで(既定は 1)。
- `normal` / `priority` ゾーンへの移動は 1 ターン、`restricted` ゾーンへの移動は 2 ターン
  (1 ターンをコネクション上で過ごし、次のターンに必ず着地する)。`blocked` ゾーンには入れない。
- 同じ長さの経路が複数あるときは `priority` ゾーンを優先する。

プログラムはマップを解析・検証し、ゴールまでの距離を計算し、ドローンの移動をターンごとに決め、
各ターンをルールに照らして検査したうえで、決められた形式でターンログを出力します。実行の様子は
ターミナル表示とグラフィカル表示(pygame-ce)の一方または両方で見られます。課題の指定どおりグラフ系
ライブラリは使っておらず、グラフ、最短経路探索、スケジューラはすべて自作です。コードはオブジェクト指向で
型注釈付きで書かれており、`flake8` と `mypy --strict` を通ります。

### Input format

マップは UTF-8 のテキストファイルです。

```text
nb_drones: 5

start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
connection: hub-roof1
connection: corridorA-tunnelB [max_link_capacity=2]
```

| 行 | 意味 |
| --- | --- |
| `nb_drones: <n>` | ドローン数(正の整数)。**ファイルの物理的な 1 行目でなければならない。** |
| `start_hub: <name> <x> <y> [metadata]` | スタートゾーン(ちょうど 1 つ)。 |
| `end_hub: <name> <x> <y> [metadata]` | エンドゾーン(ちょうど 1 つ)。 |
| `hub: <name> <x> <y> [metadata]` | 通常のゾーン。 |
| `connection: <name1>-<name2> [metadata]` | それより前に宣言された 2 つのゾーンを結ぶ双方向のコネクション。 |
| `# ...` | コメント行(行全体のみ。宣言の後ろに `#` を書くとエラー)。空行も無視する。 |

ゾーンのメタデータ(省略可、順不同): `zone=normal|blocked|restricted|priority`(既定 `normal`)、
`color=<単語>`(既定なし)、`max_drones=<n>`(既定 1)。
コネクションのメタデータ: `max_link_capacity=<n>`(既定 1)。

パーサは最初に見つけた問題で止まり、行番号と原因を表示します。主に次のものを拒否します: 1 行目が
`nb_drones:` でない、ドローン数や容量が正でない、座標が整数でない、未知のゾーン種別、未知または重複した
メタデータのキー、`[...]` ブロックの書式誤り、`-` を含むゾーン名、ゾーン名の重複、2 つ目の `start_hub` /
`end_hub`、未宣言のゾーンへのコネクション、コネクションの重複(`a-b` と `b-a` は同じもの)、
`start_hub` / `end_hub` の欠落。スタートとエンドには `zone=blocked` を指定できません。課題のとおり、
スタートとエンドの `max_drones` は受け付けたうえで無視します。スタートからエンドへ到達できないマップは、
解析の後にエラーとして報告します。

### Output format

標準出力には**ターンログだけ**を出します。1 ターン 1 行で、そのターンの移動をドローン番号順に空白区切りで並べます。

- `D<ID>-<zone>`: ドローン `<ID>` がこのターンに `<zone>` に入った(restricted ゾーンへ、
  コネクション上の 1 ターンを経て着地した場合も含む)。
- `D<ID>-<connection>`: ドローン `<ID>` が restricted ゾーンへ向けて飛び立ち、このターンはコネクション上にいる。
  コネクション名はマップでの宣言どおり(`zone_a-zone_b`)。
- 動かなかったドローンは書かれず、配送済みのドローンはもう出てきません。全機がエンドゾーンに着いたら終了します。

それ以外はすべて標準エラー出力に出ます: ターミナル表示、警告、エラー、そして最後の要約行です。要約には
総ターン数と、課題の副次的な指標のうち 2 つ(1 機あたりの平均配送ターン、1 ターンあたりの平均移動数)が入ります。

```text
summary: 5 turns, 5 drones, 4.20 turns per drone on average, 3.40 moves per turn
```

したがって `python3 fly_in.py map.txt 2>/dev/null` は、求められている出力だけを表示します。

## Instructions

### Requirements

- Python 3.10 以上(課題の要件。下記の確認は Python 3.14 で行った)。
- グラフィカル表示にのみ `pygame-ce`(2.5 以上)。pygame のそのまま置き換えられるフォークで、`pygame` として
  import される。無くても `--visual terminal` または `--visual none` なら動く。
- `make lint` / `make lint-strict` 用に `flake8` と `mypy`。
- `make test`(`tests/` の単体テスト)用に `pytest`。

すべて `requirements.txt` に書かれています。Makefile は Linux 向けです(`.venv/bin/python` を使う)。

課題と一緒に配布されるマップ(`maps.tar.gz`)はこのリポジトリに含まれていません。課題のページから
アーカイブを入手し、例えば `tar -xzf maps.tar.gz` で展開してください。リポジトリに入っているのは
`maps/subject_example.txt`(課題の例)だけです。

### Makefile

| ルール | 内容 |
| --- | --- |
| `make install` | `.venv` を作り(無い場合、または pip が使えない場合)、`requirements.txt` をインストールする。 |
| `make run` | `maps/subject_example.txt` を実行する。マップは `MAP=`、オプションは `ARGS=` で指定する。例: `make run MAP=path/to/map.txt ARGS="--visual both"`。 |
| `make debug` | 同じ実行を `pdb` の下で行う。`FLYIN_DEBUG=1` が設定され、想定外の例外が 1 行のエラーに変換されずデバッガに届く。 |
| `make lint` | `flake8 .` と、課題指定のフラグ付きの `mypy .`(`--warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs`)。 |
| `make lint-strict` | `flake8 .` と `mypy . --strict`。 |
| `make test` | `tests/` の単体テストを実行する(`pytest tests -q`)。 |
| `make clean` | `__pycache__`、`.mypy_cache`、`.pytest_cache` と `*.pyc` / `*.pyo` を消す(`.venv` の外)。 |
| `make fclean` | `clean` の後、`.venv` も消す。 |

`run`、`debug`、`lint`、`lint-strict`、`test` は、`.venv` がまだインストールされていないか `requirements.txt` が
変わったときに、先に `make install` を実行します。

### Running directly

```sh
make install
.venv/bin/python fly_in.py MAP [options]
```

| オプション | 効果 |
| --- | --- |
| `--visual {terminal,graphical,both,none}` | 実行の見せ方(既定 `terminal`)。`none` はターンログと要約だけを出す。 |
| `--delay SECONDS` | グラフィカル表示で 1 ターンを表示する秒数。0 から 60(既定 0.5)。 |
| `--step` | 1 ターンずつ進める。ターミナル表示では Enter、グラフィカル表示では右矢印キー。`both` のときはウィンドウ側で進める。ターミナル表示のステップ実行は標準入力が端末のときだけ有効なので、パイプ経由の実行が止まることはない。 |
| `--parse-only FILE` | `MAP` を解析し、解析結果のワールドを JSON で `FILE` に書いて、シミュレーションせずに終わる。 |
| `--from-world` | `MAP` をマップファイルではなく `--parse-only` が書いたワールド JSON として読み、シミュレーションする。 |
| `--save-run FILE` | 各ターンの移動とその後の状態を JSON で `FILE` に書く。`--parse-only` とは併用できない。 |
| `-h`, `--help` | ヘルプを表示して終わる。 |

**コメントで始まるマップ。** パーサは物理的な 1 行目を `nb_drones:` のヘッダとして読みます(課題:
"The first line must define the number of drones")。そのため 1 行目がコメントや空行のファイルは拒否されます。

```text
$ .venv/bin/python fly_in.py comment_first.txt
error: line 1: the first line must be 'nb_drones: <n>'
```

課題と一緒に配布されるマップはコメント行で始まります。実行するには、`nb_drones:` の行より前を取り除いた
一時ファイルを作り、それを実行してください。

```sh
sed -n '/^nb_drones:/,$p' path/to/map.txt > /tmp/map.txt
make run MAP=/tmp/map.txt
```

### Exit codes

| コード | 条件 |
| --- | --- |
| `0` | 実行が完了した(または `--parse-only` がファイルを書いた)。 |
| `1` | マップ/ワールドファイルが読めない・不正、ゴールに到達できない、グラフィカル表示が使えない(pygame が無い、ディスプレイが無い)、シミュレーションが失敗した、出力ファイルが書けない、標準出力が途中で閉じられた(例: `| head`)、または想定外の内部エラー。標準エラー出力に `error: ...` を 1 行出す。 |
| `2` | コマンドライン引数が不正(`argparse` による)。 |
| `130` | Ctrl+C で中断された。 |

実際の実行で得たエラーメッセージの例:

```text
error: cannot read map file 'nope.txt': No such file or directory
error: line 1: n must be a positive integer, got 0
error: line 3: name must not contain '-', got 'a-b'
error: line 4: zone must be one of normal, blocked, restricted, priority, got 'lava'
error: line 4: unknown zone: x
error: line 4: max_link_capacity must be a positive integer, got 0
error: line 5: duplicate connection: e-s
error: line 2: malformed metadata block
error: line 2: missing end_hub
error: goal 'e' is unreachable from 's'
error: invalid world file 'bad.json': zones: missing start_hub
fly_in.py: error: argument --delay: must be a finite number of seconds >= 0: '-1'
```

## Example

### Input

課題の例である `maps/subject_example.txt`:

```text
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

### Output

`make run ARGS="--visual none"`(または
`.venv/bin/python fly_in.py maps/subject_example.txt --visual none`):

```text
D1-corridorA D2-hub-roof1
D1-tunnelB D2-roof1 D3-corridorA D4-hub-roof1
D1-goal D2-roof2 D3-tunnelB D4-roof1 D5-corridorA
D2-goal D3-goal D4-roof2 D5-tunnelB
D4-goal D5-goal
summary: 5 turns, 5 drones, 4.20 turns per drone on average, 3.40 moves per turn
```

最初の 5 行がターンログ(標準出力)、最後の行が要約(標準エラー出力)です。経路はどちらも 3 ターンで、
`hub -> corridorA -> tunnelB -> goal`(priority ゾーン経由)と `hub -> roof1 -> roof2 -> goal`
(restricted の `roof1` に入るのに 2 ターンかかるため、`D2-hub-roof1` は D2 がコネクション上にいるターン)です。
ドローンは両方の経路に振り分けられ、5 機すべてが 5 ターンで配送されます。

## Algorithm and implementation strategy

### Pipeline

```text
map file -> MapParser -> World -> Pathfinder (DistanceMap) -> Scheduler
                                                                 |
         TurnLogPrinter, views, RunRecorder  <-  SimulationEngine + TurnResolver
```

1. **解析**(`droneflow/parsing`)。`MapReader` が行番号付きで行を渡します。`LineTokenizer` が各行の構文を
   `MapFormat`(行の種類、フィールド、既定値、変換関数を宣言的にまとめた表)に照らして検査し、分割します。
   `MapValidator` がフィールドを変換し、複数行にまたがる検査を `Rule` オブジェクトの列(名前の一意性、
   スタートとエンドが 1 つずつ、既知の端点、コネクションの一意性)に任せます。結果は `World` で、自作の
   `Network`(ゾーンと隣接リスト)とドローン数をまとめたものです。

2. **距離**(`droneflow/pathfinding`)。`DistanceMap` が、逆向きにたどったコネクション上で**エンドゾーンから
   1 回だけ Dijkstra 探索**(`heapq` を使用)を行います。あるゾーンに入るコストはそのゾーンのターンコスト
   (1、restricted なら 2)で、blocked ゾーンには入りません。これで各ゾーンからゴールまでの最小ターン数が
   得られます。容量はここでは意図的に無視します。容量はターンごとに変わり、スケジューラが扱うものだからです。
   `Pathfinder` はスタートからゴールに到達できることを確認し、ゾーンごとに 2 つの問いに答えます。
   - `next_hops`: 最短経路上の隣接ゾーン(そこに入るコストとその先の距離の和が、このゾーンの距離に等しいもの)。
     **priority ゾーンが先**、その後は宣言順。
   - `detour_hops`: 最短経路から外れるが、まだゴールに到達できる隣接ゾーン。コストの小さい順。

   距離と各ゾーンの次の一手は 1 回の実行につき 1 度だけ計算してキャッシュし、シミュレーション中に計算し直すことはありません。

3. **スケジューリング**(`droneflow/simulation/scheduling`)。`Scheduler` は毎ターン、ゾーンにいる各ドローンに
   最大 1 つの命令を出します(命令が無ければ待機)。
   - restricted ゾーンへ飛行中のドローンには命令を出さない。自動的に着地する。
   - 前のターンまでに計画され、このターンに実行すべき移動を最初に命令する。
   - 残りのドローンは `ZoneRanking` の順にゾーンごとに決める: **ゴールに近いゾーンから**(先に出ていく
     ドローンが、後ろのドローンが求める前に空きを作るため)、次に priority 経路上のゾーン、次に出口の少ない
     ゾーン(選択肢のあるドローンが、他のドローンの唯一の出口をふさがないため)、最後に宣言順。
   - ドローンは最短の一手のうち、`TurnLedger` で空きがある最初のものを取る: コネクションにこのターンの
     容量があり、入るゾーンに、入るターンと、計画された移動のある以降のすべてのターンで席があること。
   - どれにも空きがなければ、最後の手段として `Evictor` に場所を空けさせながら同じ一手を試し直す: 行き先
     ゾーンにいるドローンを、指定したターンに自分の最短の一手で先へ進むよう計画する(その行き先も満杯なら
     再帰的に)。満杯の restricted ゾーンへ飛べるのはこの仕組みによります。ドローンは次のターンに必ず着地
     するので、そのターンに今いるドローンが出ていくよう計画します。計画した移動は mark/rollback を持つ
     `ReservationTable` に保存されるので、失敗した試みは跡を残しません。
   - それも失敗したら、`DetourPolicy` が許す迂回をとれる: すでに入ったことのあるゾーンには決して入らず、
     待つより遅くならないと見込めるときだけ、つまり
     `turn_cost(v) + distance(v) + queue(v) <= distance(u) + ahead(u)` のときだけ。`ahead(u)` は最短経路上で
     先にいるドローンの数、`queue(v)` は迂回先ゾーン `v` とその先にいるドローンの数です。これにより、最短
     経路が混んでいるときにドローンが複数の経路に分散します。
   - それ以外の場合、ドローンは待機する。

   すべての実行が終わる理由は、スケジューラの docstring に書かれています: 最短の一手はゴールまでの距離を
   必ず減らし、迂回は一度も入ったことのないゾーンにしか入らないので、各ドローンの移動回数は有限です。
   さらに毎ターン少なくとも 1 機は動きます(計画された移動と着地は必ず起き、そうでなくてもゴールに最も
   近いドローンは最短経路上に必ず空きがある)。

4. **ルール検査**(`droneflow/simulation`)。`SimulationEngine` がターンのループを回します。毎ターン
   `TurnResolver` が、飛行中のドローンを着地させ、各命令(存在する・blocked でない・隣接したゾーンへ、
   1 機に 1 命令)を検査し、出発するドローンについてコネクション容量を、最終的な人数についてゾーン容量を
   検査します(同じターンにゾーンを出るドローンは入るドローンのための空きを作る。restricted ゾーンへ
   飛んだドローンは着地したターンからそこに数える)。ターン全体が合法でない限り何も反映しません。不正な
   ターン、誰も動かないターン、安全上限(`2 * ゾーン数 * ドローン数`)を超えるターン数は、エラーで実行を止めます。
   つまりスケジューラを無条件には信用しておらず、出力されたターンはすべて検査済みです。

5. **出力**(`droneflow/output`)。エンジンは毎ターンの後にオブザーバを呼びます: `TurnLogPrinter` がその
   ターンの行を標準出力に書いてフラッシュし、表示がその状態を描き、`--save-run` 指定時は `RunRecorder` が
   ターンを保存します。最後に `RunSummary` が要約行を書きます。

**コスト。** ゾーン数 Z、コネクション数 C、ドローン数 D として、Dijkstra 探索は O((Z + C) log Z) で 1 度だけ。
毎ターン、ゾーンにいる各ドローンが少数の一手を試し、それぞれを計画済みの移動がある数ターン分だけ台帳で
確認します。着地と追い出しの計画は数ターン先までしか見ません。メモリはネットワーク、距離、キャッシュした
一手、ドローンの位置に O(Z + C + D)、それに計画済みの移動の分です。

### Code structure

```text
fly_in.py                    エントリポイント: 引数、終了コード、エラー行
droneflow/
  cli.py                     コマンドラインオプション(argparse) -> Args
  app.py                     Application: 各段階をつなぐ
  errors.py                  FlyInError とそのサブクラス
  models/                    Zone, ZoneType, ZoneRole, Connection, Drone,
                             Network(自作のグラフ), World
  parsing/                   MapReader, LineTokenizer, MapFormat(行の表),
                             MapValidator, マップのルール, MapParser
  pathfinding/               DistanceMap(ゴールからの Dijkstra), Pathfinder
  simulation/                SimulationState, TurnResolver(ルール),
                             SimulationEngine(ターンループ), TurnObserver
    scheduling/              Scheduler, ZoneRanking, TurnLedger, HopTaker,
                             Evictor, ReservationTable, DetourPolicy,
                             PositionBoard
  output/                    TurnLogFormatter, TurnLogPrinter, RunSummary
  visualization/             TerminalVisualizer, GraphicalVisualizer(pygame),
                             camera, geometry, labels, palette
  interchange/               ワールドの JSON ファイルと実行記録の JSON ファイル
```

コードから読み取れる設計上の選択:

- **継承より委譲(コンポジション)を優先。** `Application` が各段階を組み合わせ、エンジンは状態、
  `TurnResolver`(ルール)、`MoveDecider`(`Scheduler`)を組み合わせ、スケジューラは小さなクラス
  (台帳、追い出し、迂回方針、順位付け)に処理を任せます。
- **接合部には Protocol。** `MoveDecider`、`TurnObserver`、`Rule` は `typing.Protocol` で、ターンログの
  出力、各表示、実行記録はすべて同じエンジンのオブザーバです。`Application` には別の決定器を差し込めます。
- **ルールと決定を分離。** スケジューラは計画し、リゾルバが検査して反映します。スケジューリングの不具合は、
  不正なターンログではなく、はっきりした `SimulationError` になります。
- **pygame を import するのは 1 モジュールだけ**(`visualization/graphical_view.py`)で、しかも遅延 import
  なので、それ以外は pygame なしで動きます。

## Visual representation

課題は、色付きのターミナル出力、グラフィカルインターフェース、またはその両方による視覚的なフィードバックを
求めています。両方を用意しており、`--visual` で選びます。

### Terminal view

既定の表示(`--visual terminal`)は、1 ターンごとに 1 フレームを標準エラー出力に書くので、標準出力の
ターンログと混ざりません。各フレームの内容:

- ターン番号、移動数、配送済み数を示すヘッダ。
- そのターンの移動。
- 全ゾーンの一覧。1 文字のタグ(`S` スタート、`E` エンド、`.` normal、`P` priority、`R` restricted、
  `X` blocked)と、負荷 `中にいる数/容量`(`-` は無制限)、そこへ飛行中のドローン `+N`、満杯を示す `*`。
- ドローンの居場所(連番は `D1..D5` のように短縮)と、飛行中のドローンがどのコネクション上でどのゾーンへ向かっているか。

ゾーン名は `color=` メタデータの色(24 ビットの ANSI カラー)で塗られます。未知の色名は端末の既定色の
ままで、満杯の数値は太字、blocked ゾーンは淡色になります。標準エラー出力が端末でないとき、または
`NO_COLOR` が設定されているときは色を付けません。`--step` では各フレームで Enter を待ちます。1 行に並べる
ゾーンの数は端末の幅で決まり、長い名前は `~` で短縮されます。

例の初期状態と最初の 2 ターン(`NO_COLOR=1`、100 桁):

```text
=== Turn 0 (start) | 5 drones | 7 zones, 6 connections ===
key: S=start E=end .=normal P=priority R=restricted X=blocked | in/max: -=no limit +N=arriving *=full
  hub       S 5/-        goal      E 0/-        roof1     R 0/1        roof2     . 0/1
  corridorA P 0/2        tunnelB   . 0/1        obstacleX X --
drones: hub[D1..D5]
=== Turn 1 | moved 2 | delivered 0/5 ===
moves: D1-corridorA D2-hub-roof1
  hub       S 3/-        goal      E 0/-        roof1     R 0/1+1*     roof2     . 0/1
  corridorA P 1/2        tunnelB   . 0/1        obstacleX X --
drones: corridorA[D1] hub[D3..D5]
in flight: D2 hub-roof1 -> roof1
=== Turn 2 | moved 4 | delivered 0/5 ===
moves: D1-tunnelB D2-roof1 D3-corridorA D4-hub-roof1
  hub       S 1/-        goal      E 0/-        roof1     R 1/1+1*     roof2     . 0/1
  corridorA P 1/2        tunnelB   . 1/1*       obstacleX X --
drones: tunnelB[D1] roof1[D2] corridorA[D3] hub[D5]
in flight: D4 hub-roof1 -> roof1
```

`roof1 R 1/1+1*` は、同じターンに D2 が出ていき D4 が入ってくる restricted ゾーンを示しています。これは
合法で、表示は容量超過のように見せるのではなく、その状況が分かるようにしています。

### Graphical view

`--visual graphical`(またはターミナル表示と一緒に `both`)は 1200x800 の pygame ウィンドウを開き、
ゾーンの座標どおり(y は上向き)にネットワークを描いて、`--delay` 秒ごとに 1 ターン再生します。

描かれるもの:

- **ゾーン**は `color=` の色で塗る(パレット、次に pygame の色名、最後に既定の灰色)。normal は円、
  priority は金色の縁、スタートとエンドは白い縁と名前の後ろの `(start)` / `(end)`、restricted は赤い縁の
  四角、blocked は濃い灰色にバツ印。
- 容量のあるゾーンの下の**負荷バー**: 埋まるにつれて緑、橙、赤と変わり、次のターンに到着するドローンの分は
  淡い色で示す。ラベルは `中にいる数/容量 +N`。エンドゾーンには配送済みの数を表示。
- **コネクション**は `max_link_capacity` に応じて太くなる線(1 より大きいと `xN` のラベル付き)で、ドローンが
  飛行中のあいだは明るくなる。同じ位置に宣言されたゾーンはその周りに広げて配置し、別のゾーンの上を通って
  しまうコネクションはそれを避ける弧として描く。
- **ドローン**は点: ゾーン内では白、コネクション上(restricted ゾーンへ飛行中、コネクションの中央に描く)では
  水色、このターンに動いたものは金色の縁。同じ点にいる複数のドローンは、数を書いた 1 つのバッジになる。
  配送済みのドローンも、同じようにゴールのゾーンに描く。
  このターンの各移動は、使ったコネクションに沿って金色の**軌跡**を残す。
- ターン、移動数、配送済み数、飛行中の数、操作方法と現在の待ち時間を示す**ステータスバー**、そのターンの
  移動を示す**フッター**(入りきらないときは `... +K more`)、マウスの下のゾーンの詳細(役割、種別、色、
  負荷、ドローン番号)を示す**ツールチップ**。

操作:

| 入力 | 効果 |
| --- | --- |
| Space | 一時停止 / 再開。 |
| 右矢印 | 待ち時間を待たずに次のターンへ(一時停止中とステップ実行中も)。 |
| 上 / `+` | 速く(待ち時間を半分に。0.05 秒を下回ると 0、つまり待たない)。 |
| 下 / `-` | 遅く(待ち時間を 2 倍に。0 のときは 0.05 秒から。上限は `--delay` と同じ 60 秒)。 |
| マウスホイール | マウス位置を中心に拡大縮小(0.5 倍から、最も近いゾーン同士が読める倍率まで)。ゾーンと文字の大きさは変わらず、間隔だけが広がる。 |
| 左ドラッグ | マップを動かす。 |
| `f` | マップ全体を表示し直す。 |
| Esc、`q`、閉じるボタン | ウィンドウを閉じる。 |

`--step` ではウィンドウが一時停止状態で始まり、右矢印で 1 ターンずつ進みます。最後のターンの後も
ウィンドウは "finished - press esc to close" と表示して開いたままです。途中でウィンドウを閉じても表示が
閉じるだけで、シミュレーションは最後まで続くので、標準出力のターンログは完全なままです。大きなマップでは、
読めないほど縮小するとゾーンは小さな点になりラベルは省かれ、拡大すると戻ります。

pygame がインストールされていない、またはウィンドウを開けない(例: ディスプレイが無い)場合、プログラムは
エラー行を 1 行出して終了コード 1 で止まります。例:
`error: the graphical view needs pygame (pygame-ce): run 'make install' or
'pip install pygame-ce', or use --visual terminal`。

## Additional features

- **読める JSON ファイルを介して、各段階を単独で実行。**
  `--parse-only world.json` は解析の後で止まり、解析したワールド(全ゾーンと全コネクションの全フィールドを
  宣言順に)を書きます。`--from-world` はそのファイルをパーサなしでシミュレーションします(マップと同じ
  ルールで検査するので、手で編集したファイルでも、パーサが拒否するようなマップがシミュレーションに渡る
  ことはない)。`--save-run run.json` は各ターン(ターン 0 は初期状態)について、ログ行、各移動、配送済み数、
  未配送の各ドローンの居場所を書きます。実行が失敗した場合は、それまでのターンを `"complete": false` で書きます。

  ```text
  $ .venv/bin/python fly_in.py maps/subject_example.txt --parse-only world.json
  world: wrote world.json (7 zones, 6 connections, 5 drones)
  $ .venv/bin/python fly_in.py world.json --from-world --visual none --save-run run.json
  D1-corridorA D2-hub-roof1
  ...
  run: wrote run.json
  summary: 5 turns, 5 drones, 4.20 turns per drone on average, 3.40 moves per turn
  ```

- 課題の副次的な指標(1 機あたりの平均ターン、1 ターンあたりの移動数)を含む**要約**を標準エラー出力に表示。
- 両方の表示での**ステップ実行**(`--step`)と、グラフィカル表示での速度変更、一時停止、拡大縮小、移動、
  マウスオーバーでの詳細表示。
- **きれいな出力ストリーム**: ターンログは 1 行ごとに標準出力へフラッシュされ、それ以外は何も書かれない
  (pygame の import 時のバナーも隠す)ので、パイプやリダイレクトに使えます。読み手が途中で閉じても
  (`| head`)トレースバックは出ません。
- **堅牢なエラー処理**: 想定内の失敗はすべて `error: ...` の 1 行と 0 以外の終了コードになります。想定外の
  例外は `error: internal error: ...` の 1 行になります(`FLYIN_DEBUG=1`、つまり `make debug` のときを除く)。

## Testing and quality

- `make lint` と `make lint-strict` は通ります: 同じコマンド(`flake8 .`、課題指定のフラグ付きの `mypy .`、
  `mypy . --strict`)をこのリポジトリで実行し、問題なしと報告されることを確認しました
  (flake8 7.4、mypy 2.4、Python 3.14)。
- クラスと公開関数には Google スタイルの docstring があり、コードはすべて型注釈付きです(`mypy --strict` で確認)。
- 実行時には `TurnResolver` が各ターンを移動と容量のルールに照らして検査してから反映するので、出力された
  ターンログは常に合法です。エンジンは、誰も動かないターンがあった場合や、安全上限のターン数を超えた場合にも止まります。
- `make test` で `tests/` の単体テストを実行します(pytest。グラフィカル表示のテストは画面なしで動き、
  pygame-ce がなければ skip します)。`tests/` は開発用のブランチにだけあり、提出用のブランチには含めていません。
- この README に示した動作(例の出力、ターミナル表示、エラーメッセージ、JSON ファイル)は、課題の例と
  小さな手書きのマップでプログラムを実行しても確認しました。

## Resources

### References

- Fly-in の課題(42、バージョン 1.6): ルール、マップ形式、出力形式、ベンチマーク。
- [Dijkstra's algorithm](https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm)(Wikipedia)。ここではゾーンごとの
  コストでエンドゾーンから使っている。
- [Python `heapq`](https://docs.python.org/3/library/heapq.html): 探索の優先度付きキュー。
- [Python `argparse`](https://docs.python.org/3/library/argparse.html)、
  [`dataclasses`](https://docs.python.org/3/library/dataclasses.html)、
  [`typing.Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol)。
- [pygame-ce のドキュメント](https://pyga.me/docs/): グラフィカル表示。
- [mypy](https://mypy.readthedocs.io/) と [flake8](https://flake8.pycqa.org/): 静的検査。
- [PEP 257](https://peps.python.org/pep-0257/)(docstring)と
  [Google Python スタイルガイド](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)。
- [ANSI エスケープコード](https://en.wikipedia.org/wiki/ANSI_escape_code)と [NO_COLOR](https://no-color.org):
  ターミナル表示の色。

### How AI was used

このプロジェクトでは全体を通して、開発者の指示のもとで AI アシスタント(Claude)を使いました。用途は、
課題の要件の分析、設計案の検討(パーサの構成、経路探索、スケジューリング、表示)、コードレビューと
不具合の発見、そして指示に従ったコードの作成です。この README も、コードと実際の実行結果をもとに AI の
助けを借りて書きました。コードはすべて開発者がレビューしており、その責任は開発者が負います。
