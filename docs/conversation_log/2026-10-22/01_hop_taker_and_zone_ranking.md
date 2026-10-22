# 2026-10-22 会話ログ: HopTaker / ZoneRanking

- 開始: 2026-10-22

## HopTaker / ZoneRanking の違い、追い出しと容量・移動時間(test/refactor_review)

- 依頼1: 「一手の試行は HopTaker、判断順は ZoneRanking」の違いを知りたい。
  - 回答要点: ZoneRanking は Scheduler 生成時に1回だけ作る、状態を持たない並び(距離, 優先ルート外, 出口数, 宣言順)。
    HopTaker はターンごとに作り、1機のホップ候補を順に試して ledger/board に記録する(追い出しなし→追い出しありの2周)。
    先に決めたドローンの記録が後のドローンの空きに効くので、順序と試行を分けている。
- 依頼2: 「先に入ってから追い出す」は容量を無視していないか。移動時間は接続に滞在する時間か。
  - 回答要点(コード確認: `hop_taker.py` `_enter_then_evict`、`turn_ledger.py`、`evictor.py`、`turn_resolver.py`):
    - 無視していない。入る前に `fits(zone, arrive, 1)` で到着ターンの空きを確認する。足りないのは後のターン
      (予定済みの進入がある)だけ。記録後に `make_room(zone, arrive + 1, 0)`(自分を数えたうえで容量以内)を
      horizon まで保証し、失敗したら `cancel` と board の復元で取り消す。「先に入る」は帳簿上の順で、
      自分自身を追い出し候補に含めるため。
    - normal/priority は出発ターン=到着ターンで、ターン終了時に接続上にはいない。restricted だけは出発ターンの終わりに
      接続上にいて、次のターンに必ず着陸する。接続容量は出発ターンだけに数える(2026-10-18 の決定)。
- 決定事項: なし。未決事項: なし。変更ファイル: 本ログのみ。

