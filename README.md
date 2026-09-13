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

したがって、全体Flow制御という上位設計は保持しつつ、局所原因掘りには戻らず Relation Flow 表現 / 作用写像を再設計します。

## 公開方針

この repository は private 研究履歴の複製ではありません。現在の実験に必要なコードと、公開してよい比較・設計だけを選んだ **curated public snapshot** です。

過去の大量の局所探索、作業用 Run marker、内部運用ファイル、不要な実験履歴は含めません。

## 実行

Python 3.11 + `kaggle-environments` を想定しています。

```bash
pip install kaggle-environments
python run_whole_flow_control.py
```

比較対象の opponent は `opponents/seyamalam_v21.py` に置く想定です。公開スナップショットでは opponent 本体は同梱せず、元リポジトリの固定 revision を利用します。
