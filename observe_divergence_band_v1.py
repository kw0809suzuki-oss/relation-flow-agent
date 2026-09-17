#!/usr/bin/env python3
"""Outside-in observer for the Day14-17 divergence band.

No policy mutation. Compare high/low terminal cases only on state variables already
exported by scale_baseline_v1. This narrows where the waterway separates before
asking which local action/product caused it.
"""
import json
from pathlib import Path

SRC=Path('scale_baseline_v1.json')
OUT=Path('divergence_band_v1.json')
DAYS=range(12,19)


def avg(xs): return sum(xs)/len(xs) if xs else None

def day_summary(cases, day):
    rows=[]
    for c in cases:
        r=next((x for x in c['observations'] if x['day']==day),None)
        if r: rows.append(r)
    return {
        'day':day,'count':len(rows),
        'money':avg([r['money'] for r in rows]),
        'land':avg([r['land'] for r in rows]),
        'hands':avg([r['hands'] for r in rows]),
        'animals':avg([r['animals'] for r in rows if r['animals'] is not None]),
        'stock_value':avg([r['produced_value'] for r in rows]),
        'positive_money_delta':avg([r['collected_value'] for r in rows]),
    }

def main():
    data=json.loads(SRC.read_text())
    ranked=sorted(data['cases'],key=lambda c:c['terminal']['self'],reverse=True)
    n=len(ranked)//3
    high,low=ranked[:n],ranked[-n:]
    hs=[day_summary(high,d) for d in DAYS]
    ls=[day_summary(low,d) for d in DAYS]
    comparisons=[]
    for h,l in zip(hs,ls):
        comparisons.append({
            'day':h['day'],
            'money_gap':h['money']-l['money'],
            'land_gap':h['land']-l['land'],
            'hands_gap':h['hands']-l['hands'],
            'animals_gap':h['animals']-l['animals'],
            'stock_value_gap':h['stock_value']-l['stock_value'],
            'positive_money_delta_gap':h['positive_money_delta']-l['positive_money_delta'],
        })
    out={
        'coordinate':'whole capital flow -> Day12-18 divergence band -> first state dimension where high/low terminal groups separate',
        'policy_mutated':False,
        'boundary':'descriptive group averages only; no causal attribution and produced_value is market-valued inventory stock',
        'high_seeds':[c['seed'] for c in high],
        'low_seeds':[c['seed'] for c in low],
        'high':hs,'low':ls,'gap_high_minus_low':comparisons,
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print('DIVERGENCE_BAND_V1 '+json.dumps(comparisons,separators=(',',':')))
if __name__=='__main__': main()
