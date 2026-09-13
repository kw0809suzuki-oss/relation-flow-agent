# V2 Vector Relation Flow — PRE-REGISTERED

## 外側の目的

terminal score を上げる。

## 今回の1設計単位

V1では `money / capacity / public_production` を平均して1つの scalar relation score に潰していた。

V2では軸を潰さず、**3軸の符号と3軸の変化方向を2-of-3多数決で保持する**。

変更するのは Relation Flow 表現だけ。

- relation axes: unchanged
- gate mapping: unchanged (`push=.04 / maintain=.04 / stop=.02 / switch=0.0`)
- Native Origin: unchanged
- existing action candidates: unchanged
- 12 seed/seat cases: unchanged
- V1 horizon implementation: intentionally unchanged for isolation

## V2 mode

```text
relation favorable votes >= 2
movement favorable votes >= 2
    -> push

relation favorable votes >= 2
movement favorable votes < 2
    -> stop

relation favorable votes < 2
movement favorable votes >= 2
    -> maintain

relation favorable votes < 2
movement favorable votes < 2
    -> switch
```

## Runtime boundary

seed / paired difference / terminal reward / future state は runtime 制御入力に使わない。

## 判定

まず12ケース探索。

- mean margin delta
- win delta
- improved / worsened / equal
- max downside
- action-difference cases / count

をV1と同じ面で見る。

**結果を見てからV2定義を変更しない。**

有望なら24〜50ケースへ拡張。弱ければCUT。混在して次の意思決定が変わる場合だけPROBE。
