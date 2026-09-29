# Kaggriculture｜終端回収型運転モデル v0｜並列試走

## 目的

Official World上で terminal self を上げる。

現在のStrongを基準に、Return Stage と Work Allocation の変更を独立variantとして並列比較する。

## 実験単位

同一seed、同一seat、同一Opponent、同一Bodyから次のvariantを生成する。

- V0: 現在のStrongを維持
- V1: Harvest可能なOutputを優先
- V2: Carry中OutputのShed搬入を優先
- V3: Shed内OutputのSELLを優先
- V4: 新規投資を抑え、既存運転の回収を優先
- V5: 空いているWorkerだけを回収へ再配分

各variantは独立して実行する。variant同士の結果を入力にしない。

## 24手ゲート

各variantについて、最初の24 agent observationsを保存する。

記録するもの:

- action sequence
- worker position / current work
- productive asset state
- harvestable output
- carried output
- shed inventory
- sell-ready output
- cash
- active commitments

24手ではterminal採否を決めない。World上で運転が動いたvariantだけterminal比較へ進める。

運転が動いた、とは次のいずれかを意味する。

- Return Stageが一段進んだ
- Worker allocationが変わり、対象のStateが変わった
- CarryまたはShed滞留が変わった
- SELL準備またはCash回収が変わった

Action列だけが変わり、World Stateが変わらないvariantはterminalへ送らない。

## terminal比較

24手ゲート通過variantを同じ条件で720-turn Battleへ送る。

Primary metric:

- terminal self

補助記録:

- terminal margin
- win / loss
- first World divergence
- Return Stage別の最終残量

terminal selfが基準を上回ったvariantだけを採用候補とする。悪化variantには救済調整を加えない。

## 実装境界

既存のFrozen Originと既存Strongの判断本体は直接書き換えない。

variant差分は、現在のaction生成後に適用できる最小の運転配分フックとして実装する。variant適用ができない状態では、V0だけを正本として扱い、他variantを同一結果で通過させない。

## 現在のEvidence

同じ物理MILK総量でも、COW上、Carry、Shedの配分が変わり、その後のSELL境界が変わる記録がある。最初の差の直前には、Harvest可能なCOWへのWork Allocation差が観測されている。

このEvidenceはvariant生成の入口であり、特定のHarvest規則が強いことの証明ではない。

## 出力

runnerはvariantごとに次を出力する。

- variant id
- gate status
- first World divergence
- 24手State summary
- terminal self
- terminal margin
- decision: adopt / reject / unresolved

実験結果が返った時点で、親目的である terminal self の改善へ戻り、variant単位で採用・棄却を決める。
