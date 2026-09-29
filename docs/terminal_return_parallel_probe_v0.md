# Kaggriculture｜終端回収型運転モデル v0｜並列試走

## 目的

Official World上で terminal self を上げる。

現在のStrongを基準に、Return Stage と Work Allocation の変更を独立variantとして並列比較する。

## 実装境界

現行 planner の既存経路を使う。

planned commitments → _service_action() → Action → rollout()

Action生成後にActionを書き換える新しいhookは作らない。各variantは、次の入力差分だけを返す。

- planned commitments
- forced
- harvest_now

既存の _service_action()、schedule()、unit_action()、rollout() はそのまま使う。

operating_jobs() は毎回自動追加されるため、v0では稼働中Jobの強制停止を扱わない。まず commitments の配分変更だけを比較する。

## 並列variant

- V0: active commitmentsを維持
- V1: active + Harvest可能な既存資産1件
- V2: active + Carry中Outputの搬入候補1件
- V3: active + Shed内OutputのSELL候補
- V4: activeから既存commitmentを1件縮小
- V5: active + 空いているWorkerで回収候補1件

候補が存在しないvariantは無理に生成せず、判定不能として記録する。

## 24手ゲート

同一seed、同一seat、同一Opponent、同一Bodyから各variantを独立実行する。

記録するもの:

- planned commitments
- action sequence
- worker position / current work
- productive asset state
- harvestable output
- carried output
- shed inventory
- sell-ready output
- cash
- active commitments

24手ではterminal採否を決めない。World上で運転が動いたvariantだけterminal比較へ進める。Action列だけが変わり、World Stateが変わらないvariantはterminalへ送らない。

## terminal比較

24手ゲート通過variantを同じ条件で720-turn Battleへ送る。

Primary metricはterminal self。補助記録としてterminal margin、win/loss、first World divergence、Return Stage別の最終残量を保存する。

terminal selfが基準を上回ったvariantだけを採用候補とする。悪化variantには救済調整を加えない。

## 現在のEvidence

同じ物理MILK総量でも、COW上、Carry、Shedの配分が変わり、その後のSELL境界が変わる記録がある。最初の差の直前には、Harvest可能なCOWへのWork Allocation差が観測されている。

このEvidenceは候補生成の入口であり、特定のHarvest規則が強いことの証明ではない。

## 出力

runnerはvariantごとに次を出力する。

- variant id
- gate status
- first World divergence
- 24手State summary
- terminal self
- terminal margin
- decision: adopt / reject / unresolved

結果が返ったらvariant単位で採否を決め、terminal selfの親目的へ戻る。
