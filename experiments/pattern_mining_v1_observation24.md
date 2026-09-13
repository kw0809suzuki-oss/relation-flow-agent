# Pattern Mining v1 — Observation Batch 24

## 外側の目的

試合全体のRelation Flowを認識し、そのFlowへ作用してterminal scoreを上げる。

今回の目的はscore改善ではなく、その前段としてWhole Flowから複数パターンを広く拾い、Pattern Bundleとして保持できる観測面を作ること。

## Pattern Mining v1のどこを試すか

`Whole Flow観測 → pattern複数抽出 → Pattern Bundle`

ここまで。作用候補・制御写像はまだ作らない。

## Cases

- fresh seeds: 3264–3287
- 24 cases
- seat 0/1 alternating
- terminal結果を見てseedを選ばない

## 観測面

- self public state
- opponent public state
- self private inventory
- market prices / inventory
- action
- day-to-day time change

最初から単一scoreへ圧縮しない。

## Pattern Bundle

各数値seriesについて、

- start / end / net
- up / down / flat のdirection run
- direction transition
- 同一day intervalで同時に変化したdimension集合
- action profile

を保持する。

これは良否ラベルではなく、後段で束ねるための記述単位。

## Result-blind boundary

Pattern Bundleを構築し終えてからterminal rewardを読む。
Pattern構築に以下を使わない。

- seed
- paired difference
- terminal reward
- future state

## 今回しないこと

- maintain / push / stop / switch / wait へのmapping
- scoreでpatternを選別
- 因果帰属
- 局所原因掘り
- 閾値最適化

## 次の判断

24 Bundleを観測後、まず複数試合を束ねる。
共通、反例、例外、未知形を同時に残す。
その束ね方がterminal score改善の次の意思決定に繋がる場合だけ作用実験へ進む。
