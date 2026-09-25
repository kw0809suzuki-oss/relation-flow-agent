#!/usr/bin/env python3
"""Aggregate WR-01 / WR-02 / Bundle fixed-five comparison v1."""
import glob,json,statistics
from pathlib import Path

ARMS=("baseline","wr01","wr02","bundle")
def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

def main():
    ps=sorted(Path(p) for p in glob.glob(
        "wr-component-v1-artifacts/**/world_reference_component_comparison_v1_*.json",
        recursive=True
    ))
    if len(ps)!=5:
        raise SystemExit(f"Expected 5 artifacts, found {len(ps)}")
    rs=[json.loads(p.read_text(encoding="utf-8")) for p in ps]

    base=[float(r["baseline"]["terminal"]["self"]) for r in rs]
    arms={}
    for arm in ARMS:
        vals=[float(r[arm]["terminal"]["self"]) for r in rs]
        margins=[float(r[arm]["terminal"]["margin"]) for r in rs]
        deltas=[v-b for v,b in zip(vals,base)]
        arms[arm]={
            "absolute_mean_self":mean(vals),
            "delta_mean_vs_baseline":mean(deltas),
            "delta_median_vs_baseline":median(deltas),
            "improved_cases":sum(x>0 for x in deltas),
            "worsened_cases":sum(x<0 for x in deltas),
            "equal_cases":sum(x==0 for x in deltas),
            "min_delta":min(deltas),
            "max_delta":max(deltas),
            "absolute_mean_margin":mean(margins),
            "by_seed":{str(r["seed"]):d for r,d in zip(rs,deltas)},
        }

    bundle=[float(r["bundle"]["terminal"]["self"]) for r in rs]
    wr01=[float(r["wr01"]["terminal"]["self"]) for r in rs]
    wr02=[float(r["wr02"]["terminal"]["self"]) for r in rs]

    payload={
        "schema":"kaggriculture.strong-origin-v2.world-reference-component-comparison.result.v1",
        "battle_count":5,
        "arms":arms,
        "ablation_view":{
            "bundle_minus_wr01_mean":mean([u-a for u,a in zip(bundle,wr01)]),
            "bundle_minus_wr02_mean":mean([u-a for u,a in zip(bundle,wr02)]),
            "bundle_minus_wr01_by_seed":{str(r["seed"]):u-a for r,u,a in zip(rs,bundle,wr01)},
        },
        "connection":{
            "wr01_reopened_orders_total":sum(int(r["connection"]["wr01_reopened_orders"]) for r in rs),
            "wr02_duplicate_seen_total":sum(int(r["connection"]["wr02_duplicate_seen"]) for r in rs),
            "wr02_moved_total":sum(int(r["connection"]["wr02_moved"]) for r in rs),
            "bundle_wr01_reopened_orders_total":sum(int(r["connection"]["bundle_wr01_reopened_orders"]) for r in rs),
            "bundle_wr02_duplicate_seen_total":sum(int(r["connection"]["bundle_wr02_duplicate_seen"]) for r in rs),
            "bundle_wr02_moved_total":sum(int(r["connection"]["bundle_wr02_moved"]) for r in rs),
        },
        "cases":[{
            "seed":r["seed"],"seat":r["seat"],
            "baseline":r["baseline"]["terminal"],
            "wr01":r["wr01"]["terminal"],
            "wr02":r["wr02"]["terminal"],
            "bundle":r["bundle"]["terminal"],
            "delta_self":r["delta_self"],
            "connection":r["connection"],
        } for r in rs],
        "boundary":[
            "Fixed-five first-pass comparison only.",
            "Every arm records baseline absolute mean self / candidate absolute mean self / delta.",
            "Ablation view is direct Battle difference; no additive contribution assumption is made.",
            "Independent validation is required before retaining a new component."
        ]
    }
    Path("world_reference_component_comparison_v1_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("WR_COMPONENT_COMPARISON_V1_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
