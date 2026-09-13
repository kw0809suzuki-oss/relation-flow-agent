# Relation Flow Pattern Mining v1

> 先に世界を豊かに観測する。後から束ねる。最後にだけ制御する。

## 外側の目的

Pattern抽出そのものが目的ではない。

**試合全体のRelation Flowを認識し、そのFlowへ作用してterminal scoreを上げること。**

単一のRelation指標、閾値、局所原因探しを目的化しない。

## 観測から制御まで

1. **Whole Flowを広く観測する**
   - self
   - opponent
   - market
   - money
   - production
   - capacity
   - feed
   - animals
   - action
   - 時間変化
   - 最初から一つのscoreへ圧縮しない

2. **複数の変化パターンを拾う**
   - 優勢形成 / 保持 / 崩壊 / 反転 / 再形成
   - 自分だけ伸びる / 相手だけ沈む
   - 両方伸びる / 両方沈む
   - market連動
   - action後にgapが開く / 閉じる
   - 一時改善→崩壊
   - 遅れて効く
   - 無変化
   - ここにない形も閉じずに拾う

3. **1試合をPattern Bundleとして保持する**
   - 単一ラベルにしない
   - 前半 / 中盤 / 後半 / action後 / market / terminalなど、複数の関係を一つのBundleとして持つ

4. **多数試合を束ねる**
   - 似たBundleを集める
   - 共通部分を見る
   - 違いも残す
   - 改善群だけでなく悪化群・反例・例外も同時に保持する

5. **候補構造を立てる**
   - ここまでは観測・記述
   - まだ直接の良否判断器にしない

6. **ここで初めて作用候補へ落とす**
   - maintain
   - push
   - stop
   - switch
   - wait

7. **実験する**

   `Pattern Bundle → action effect → whole Flow変化 → terminal`

8. **評価する**
   - terminal scoreが改善するか
   - 広いseed / seatで保持されるか
   - 大悪化が増えていないか
   - 反例が多すぎないか
   - action差がterminalへ届いているか

9. **Re-entry**
   - 効く構造 → 残す
   - 効かない表現 → Cut
   - 未確定 → 未確定のまま保持

## 実験原則

- **1実験 = 1設計単位**。1変数に限定しない。
- 探索段階では、相互依存する複数要素を一つの設計Bundleとして変更してよい。
- 有望候補が立った後の確認段階で必要に応じて分解する。
- 各実験の冒頭に、**「Pattern Mining v1のどこを試しているか」**を明記する。
- 実験前に変更点 / 固定点 / baseline / cases / metrics / forbidden runtime inputsを固定する。
- 結果を見てから設計理由を後付けしない。

## 現在地

- V1 scalar mean Relation表現: Cut
- V2 3軸vector多数決: 24ケース拡張で既存12平均 +477.92、追加12平均 -236.83。広いFieldで優位傾向を再現せず、V2多数決表現のみCut。
- **whole Relation Flow構造そのものは継続。**

## 実行場所

- **主要な実験の遊び場 / runnerは現在のChatGPTローカル・ツール環境（「こっち」）。**
- このpublic repositoryは、ソース / 保存 / 公開 / 必要時の再現確認のために使う。
- GitHub Actionsを主要実験runnerにしない。明示的に再現確認を行う場合だけ使う。
- private `flow-hand` は過去研究のアーカイブ。

## Re-entry Key

`外側の目的 → Whole Flow観測 → pattern複数抽出 → Pattern Bundle → 束ねる → 候補構造 → 作用候補 → terminal照合`

この順序を飛ばして、局所指標・単一score・面白い現象そのものへ目的を移さない。
