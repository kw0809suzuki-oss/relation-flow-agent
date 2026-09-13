# relation-flow-agent

Kaggriculture を対象に、**試合全体を Relation Flow として認識し、その Flow に粗く作用して terminal score の改善を試す**公開実験リポジトリです。

## 外側の目的

スコアを上げる。

最上位の判定はこれです。

> この観測・実験は、スコアを上げるための次の意思決定を変えるか。変えないなら、正しくてもやらない。

## 上位設計

```text
試合全体を認識
→ Relation Flow を形成
→ 既存 action へ粗く作用
→ terminal で直接評価
```

Runtime では seed、paired difference、terminal reward、future State を制御入力に使いません。Native Origin と既存 action 候補を保持し、Relation Flow は作用強度だけを調整します。

## 現在地

第1 Whole Relation Flow controller では、作用経路

```text
全体Flow認識 → gate強度変更 → action → terminal
```

が成立することを確認しました。ただし12ケース比較ではスコア改善に至らず、第1作用写像は Cut としました。

- mean margin delta: `-944.67`
- win: `0/12 → 0/12`
- improved / worsened / equal: `4 / 2 / 6`
- action difference cases: `6/12`
- total action differences: `2233`
- max improvement: `+3854`
- max worsening: `-17149`

この数値は private 側の成功済み V1 Run artifact と照合済みです。

### V1 実装上の注記

V1 は Flow horizon を「24 agent observations」と記述していますが、実装では `deque(maxlen=DAY_CALLS + 1)` と `history[0]` を組み合わせているため、warmup 後の比較距離は実質 25 observations になります。V1 の結果はこの実装で得られた観測事実として保持し、結果を書き換えるための後付け修正は行いません。次版で horizon を再定義する場合は別実験として扱います。

したがって、全体Flow制御という上位設計は保持しつつ、局所原因掘りには戻らず Relation Flow 表現 / 作用写像を再設計します。

## 公開方針

この repository は private 研究履歴の複製ではありません。現在の実験に必要なコードと、公開してよい比較・設計だけを選んだ **curated public snapshot** です。

過去の大量の局所探索、作業用 Run marker、内部運用ファイル、不要な実験履歴は含めません。

## 実行

Python 3.11 + `kaggle-environments` を想定しています。

```bash
pip install -r requirements.txt
bash scripts/fetch_opponent.sh
python run_whole_flow_control.py
```

比較対象の opponent は `opponents/seyamalam_v21.py` に置きます。opponent 本体は同梱せず、`scripts/fetch_opponent.sh` が元リポジトリの固定 revision を取得します。
