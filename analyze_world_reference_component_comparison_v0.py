#!/usr/bin/env python3
"""Aggregate WR component comparison fixed5."""
import glob,json,statistics
from pathlib import Path

ARMS=("baseline","wr01","wr02","bundle")
def mean(xs): return sum(xs)/len(xs) if xs else None
def med(xs): return statistics.median(xs) if xs else None

def main():
    ps=sorted(Path(p) for p in glob.glob("wr-component-artifacts/**/world_reference_component_comparison_v0_*.json",recursive=True))
    if len(ps)!=5: raise SystemExit(f"Expected 5 artifacts, found {len(ps)}")
    raws=[json.loads(p.read_text()) for p in ps]
    base=[float(r["baseline"]["terminal"]["self"]) for r in raws]
    summary={}
    for arm in ARMS:
        vals=[float(r[arm]["terminal"]["self"]) for r in raws]
        deltas=[v-b for v,b in zip(vals,base)]
        margins=[float(r[arm]["terminal"]["margin"]) for r in raws]
        summary[arm]={
            "absolute_mean_self":mean(vals),
            "delta_mean_vs_baseline":mean(deltas),
            "delta_median_vs_baseline":med(deltas),
            "improved_cases":sum(x>0 for x in deltas),
            "worsened_cases":sum(x<0 for x in deltas),
            "equal_cases":sum(x==0 for x in deltas),
            "min_delta":min(deltas),
            "max_delta":max(deltas),
            "absolute_mean_margin":mean(margins),
            "by_seed":{str(r["seed"]):d for r,d in zip(raws,deltas)},
        }
    payload={
        "schema":"kaggriculture.strong-origin-v2.world-reference-component-comparison.result.v0",
        "battle_count":5,
        "arms":summary,
        "connection":{
            "wr01_reopened_orders_total":sum(int(r["connection"]["wr01_reopened_orders"]) for r in raws),
            "wr02_reopened_land_orders_total":sum(int(r["connection"]["wr02_reopened_land_orders"]) for r in raws),
            "wr02_cases_with_reopened_land":sum(int(r["connection"]["wr02_reopened_land_orders"])>0 for r in raws),
            "bundle_wr01_reopened_orders_total":sum(int(r["connection"]["bundle_wr01_reopened_orders"]) for r in raws),
            "bundle_wr02_reopened_land_orders_total":sum(int(r["connection"]["bundle_wr02_reopened_land_orders"]) for r in raws),
        },
        "cases":[{
            "seed":r["seed"],"seat":r["seat"],
            "baseline":r["baseline"]["terminal"],
            "wr01":r["wr01"]["terminal"],
            "wr02":r["wr02"]["terminal"],
            "bundle":r["bundle"]["terminal"],
            "delta_self":r["delta_self"],
            "connection":{
                "wr01_reopened_orders":r["connection"]["wr01_reopened_orders"],
                "wr02_reopened_land_orders":r["connection"]["wr02_reopened_land_orders"],
                "bundle_wr01_reopened_orders":r["connection"]["bundle_wr01_reopened_orders"],
                "bundle_wr02_reopened_land_orders":r["connection"]["bundle_wr02_reopened_land_orders"],
            }
        } for r in raws],
        "boundary":[
            "Fixed-five comparison only; no arm is finally adopted from this result alone.",
            "Each arm reports baseline absolute mean self / candidate absolute mean self / delta through the shared baseline.",
            "Bundle interaction is empirical Battle outcome; no additive assumption is made."
        ]
    }
    Path("world_reference_component_comparison_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
    print("WR_COMPONENT_COMPARISON_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
