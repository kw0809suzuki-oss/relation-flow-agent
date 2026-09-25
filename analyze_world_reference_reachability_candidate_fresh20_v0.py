#!/usr/bin/env python3
"""Aggregate World Reference Reachability Candidate v0 independent fresh20 A/B."""
import glob,json,statistics
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

def main():
    paths=sorted(Path(p) for p in glob.glob(
        "world-reference-reachability-fresh20-artifacts/**/world_reference_reachability_candidate_v0_*.json",
        recursive=True,
    ))
    if len(paths)!=20:
        raise SystemExit(f"Expected 20 artifacts, found {len(paths)}")
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

    b=[float(r["baseline"]["terminal"]["self"]) for r in raws]
    c=[float(r["candidate"]["terminal"]["self"]) for r in raws]
    d=[x-y for x,y in zip(c,b)]

    bm=[float(r["baseline"]["terminal"]["margin"]) for r in raws]
    cm=[float(r["candidate"]["terminal"]["margin"]) for r in raws]
    dm=[x-y for x,y in zip(cm,bm)]

    reopened=[int(r["connection_telemetry"]["reopened_orders"]) for r in raws]
    by_key={}
    for r in raws:
        for k,v in r["connection_telemetry"]["reopened_by_key"].items():
            by_key[k]=by_key.get(k,0)+int(v)

    payload={
        "schema":"kaggriculture.strong-origin-v2.world-reference-reachability-candidate.fresh20.result.v0",
        "battle_count":len(raws),
        "seed_range":[min(int(r["seed"]) for r in raws),max(int(r["seed"]) for r in raws)],
        "terminal_self":{
            "baseline_absolute_mean":mean(b),
            "candidate_absolute_mean":mean(c),
            "delta_mean":mean(d),
            "delta_median":median(d),
            "delta_min":min(d),
            "delta_max":max(d),
            "improved_cases":sum(x>0 for x in d),
            "worsened_cases":sum(x<0 for x in d),
            "equal_cases":sum(x==0 for x in d),
            "by_seed":{str(r["seed"]):x for r,x in zip(raws,d)},
        },
        "terminal_margin":{
            "baseline_absolute_mean":mean(bm),
            "candidate_absolute_mean":mean(cm),
            "delta_mean":mean(dm),
        },
        "connection":{
            "reopened_orders_total":sum(reopened),
            "reopened_orders_mean":mean(reopened),
            "cases_with_reopening":sum(x>0 for x in reopened),
            "reopened_by_key_total":dict(sorted(by_key.items())),
        },
        "cases":[{
            "seed":r["seed"],
            "seat":r["seat"],
            "baseline":r["baseline"]["terminal"],
            "candidate":r["candidate"]["terminal"],
            "delta":r["terminal_delta"],
            "reopened_orders":r["connection_telemetry"]["reopened_orders"],
            "reopened_by_key":r["connection_telemetry"]["reopened_by_key"],
        } for r in raws],
        "boundary":[
            "This is independent fresh20 validation of the unchanged Candidate v0.",
            "No trigger, threshold, product selection, or policy logic was changed after the fixed-five result.",
            "Candidate retains only native BUY_SEED / BUY_ANIMAL orders that are terminal-reachable by public first-output schedule.",
            "Terminal self is the primary adoption criterion."
        ]
    }
    Path("world_reference_reachability_candidate_fresh20_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("WORLD_REFERENCE_REACHABILITY_CANDIDATE_FRESH20_RESULT "+json.dumps({
        "terminal_self":payload["terminal_self"],
        "terminal_margin":payload["terminal_margin"],
        "connection":payload["connection"],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
