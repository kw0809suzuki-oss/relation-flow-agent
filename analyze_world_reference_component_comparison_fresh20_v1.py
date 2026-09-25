#!/usr/bin/env python3
"""Reconstruct independent fresh20 four-arm comparison from prior WR-01 result + new WR-02/Bundle runs."""
import glob,json,statistics
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

def main():
    prior=json.loads(Path("world_reference_reachability_candidate_fresh20_v0_result.json").read_text(encoding="utf-8"))
    ps=sorted(Path(p) for p in glob.glob("wr02-bundle-fresh20-artifacts/**/wr02_bundle_fresh20_v0_*.json",recursive=True))
    if len(ps)!=20: raise SystemExit(f"Expected 20 new artifacts, found {len(ps)}")
    new=[json.loads(p.read_text(encoding="utf-8")) for p in ps]
    prior_by={int(r["seed"]):r for r in prior["cases"]}
    new_by={int(r["seed"]):r for r in new}
    seeds=sorted(prior_by)
    if seeds!=sorted(new_by): raise SystemExit("Seed mismatch between prior and new fresh20")

    rows=[]
    for seed in seeds:
        p=prior_by[seed]; n=new_by[seed]
        rows.append({
            "seed":seed,"seat":n["seat"],
            "baseline":p["baseline"],
            "wr01":p["candidate"],
            "wr02":n["wr02"]["terminal"],
            "bundle":n["bundle"]["terminal"],
            "connection":n["connection"],
        })

    base=[float(r["baseline"]["self"]) for r in rows]
    arms={}
    for arm in ("baseline","wr01","wr02","bundle"):
        vals=[float(r[arm]["self"]) for r in rows]
        margins=[float(r[arm]["margin"]) for r in rows]
        ds=[v-b for v,b in zip(vals,base)]
        arms[arm]={
            "absolute_mean_self":mean(vals),
            "delta_mean_vs_baseline":mean(ds),
            "delta_median_vs_baseline":median(ds),
            "improved_cases":sum(x>0 for x in ds),
            "worsened_cases":sum(x<0 for x in ds),
            "equal_cases":sum(x==0 for x in ds),
            "min_delta":min(ds),"max_delta":max(ds),
            "absolute_mean_margin":mean(margins),
            "by_seed":{str(r["seed"]):d for r,d in zip(rows,ds)},
        }

    bundle=[float(r["bundle"]["self"]) for r in rows]
    wr01=[float(r["wr01"]["self"]) for r in rows]
    wr02v=[float(r["wr02"]["self"]) for r in rows]
    payload={
        "schema":"kaggriculture.strong-origin-v2.world-reference-component-comparison.fresh20.result.v1",
        "battle_count":20,
        "seed_range":[min(seeds),max(seeds)],
        "arms":arms,
        "ablation_view":{
            "bundle_minus_wr01_mean":mean([u-a for u,a in zip(bundle,wr01)]),
            "bundle_minus_wr01_median":median([u-a for u,a in zip(bundle,wr01)]),
            "bundle_minus_wr01_positive_cases":sum(u>a for u,a in zip(bundle,wr01)),
            "bundle_minus_wr01_negative_cases":sum(u<a for u,a in zip(bundle,wr01)),
            "bundle_minus_wr02_mean":mean([u-a for u,a in zip(bundle,wr02v)]),
            "bundle_minus_wr02_positive_cases":sum(u>a for u,a in zip(bundle,wr02v)),
            "bundle_minus_wr02_negative_cases":sum(u<a for u,a in zip(bundle,wr02v)),
        },
        "connection":{
            "wr02_duplicate_seen_total":sum(int(r["connection"]["wr02_duplicate_seen"]) for r in rows),
            "wr02_moved_total":sum(int(r["connection"]["wr02_moved"]) for r in rows),
            "bundle_wr01_reopened_orders_total":sum(int(r["connection"]["bundle_wr01_reopened_orders"]) for r in rows),
            "bundle_wr02_duplicate_seen_total":sum(int(r["connection"]["bundle_wr02_duplicate_seen"]) for r in rows),
            "bundle_wr02_moved_total":sum(int(r["connection"]["bundle_wr02_moved"]) for r in rows),
        },
        "cases":[{
            **r,
            "delta_self":{
                arm:float(r[arm]["self"])-float(r["baseline"]["self"])
                for arm in ("wr01","wr02","bundle")
            }
        } for r in rows],
        "boundary":[
            "Independent fresh20 matched on seeds 8201-8220 and alternating seats.",
            "Baseline and WR-01 values come from the previously completed unchanged WR-01 fresh20 run.",
            "WR-02 and Bundle logic are unchanged after the fixed-five comparison.",
            "Terminal self is primary; ablation differences determine whether each component earns retention."
        ]
    }
    Path("world_reference_component_comparison_fresh20_v1_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("WR_COMPONENT_COMPARISON_FRESH20_V1_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
