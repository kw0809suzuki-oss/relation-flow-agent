#!/usr/bin/env python3
"""Aggregate Terminal-Reachable Asset Surface v0 fixed-five observations."""
import glob,json,statistics
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

def metric(raws,key):
    sv=[float(r["self"]["summary"][key]) for r in raws]
    ov=[float(r["opponent"]["summary"][key]) for r in raws]
    gaps=[o-s for s,o in zip(sv,ov)]
    return {
        "self_absolute_mean":mean(sv),
        "opponent_absolute_mean":mean(ov),
        "mean_residual_opponent_minus_self":mean(gaps),
        "median_residual_opponent_minus_self":median(gaps),
        "opponent_ahead_cases":sum(x>0 for x in gaps),
        "self_ahead_cases":sum(x<0 for x in gaps),
        "equal_cases":sum(x==0 for x in gaps),
        "min_residual":min(gaps),
        "max_residual":max(gaps),
        "by_seed":{str(r["seed"]):g for r,g in zip(raws,gaps)},
    }

def by_asset_type(raws):
    types=sorted(set(
        z["asset_type"]
        for r in raws
        for side in ("self","opponent")
        for z in r[side]["assets"]
    ))
    out={}
    for typ in types:
        out[typ]={}
        for cls in ("ready_mark","reachable_mark","not_reachable_mark"):
            sv=[];ov=[]
            for r in raws:
                sv.append(sum(float(z[cls]) for z in r["self"]["assets"] if z["asset_type"]==typ))
                ov.append(sum(float(z[cls]) for z in r["opponent"]["assets"] if z["asset_type"]==typ))
            gaps=[o-s for s,o in zip(sv,ov)]
            out[typ][cls]={
                "self_absolute_mean":mean(sv),
                "opponent_absolute_mean":mean(ov),
                "mean_residual_opponent_minus_self":mean(gaps),
            }
    return out

def main():
    paths=sorted(Path(p) for p in glob.glob(
        "terminal-reachable-artifacts/**/terminal_reachable_asset_surface_v0_*.json",
        recursive=True
    ))
    if len(paths)!=5:
        raise SystemExit(f"Expected 5 artifacts, found {len(paths)}")
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

    integrity=[]
    for r in raws:
        for side in ("self","opponent"):
            err=float(r[side]["summary"]["decomposition_error_vs_existing_basis"])
            integrity.append({"seed":r["seed"],"side":side,"error":err})
            if abs(err)>1e-9:
                raise SystemExit(f"Decomposition mismatch seed={r['seed']} side={side}: {err}")

    ready=metric(raws,"ready_mark")
    reachable=metric(raws,"reachable_mark")
    not_reachable=metric(raws,"not_reachable_mark")
    committed=metric(raws,"committed_mark_existing_basis")

    residual_parts=(
        ready["mean_residual_opponent_minus_self"]
        + reachable["mean_residual_opponent_minus_self"]
        + not_reachable["mean_residual_opponent_minus_self"]
    )
    total_residual=committed["mean_residual_opponent_minus_self"]

    payload={
        "schema":"kaggriculture.strong-origin-v2.terminal-reachable-asset-surface.result.v0",
        "battle_count":len(raws),
        "anchor":{"day":20,"hour":0,"terminal_day":raws[0]["anchor"]["terminal_day"]},
        "terminal_absolute":{
            "mean_self":mean([float(r["terminal"]["self"]) for r in raws]),
            "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in raws]),
            "mean_margin":mean([float(r["terminal"]["margin"]) for r in raws]),
        },
        "day20_committed_production_decomposition":{
            "ready":ready,
            "reachable":reachable,
            "not_reachable":not_reachable,
            "existing_committed_production":committed,
            "residual_reconstruction":{
                "parts_sum":residual_parts,
                "existing_total":total_residual,
                "error":residual_parts-total_residual,
            },
            "reachable_share_of_opponent_minus_self_committed_residual":(
                reachable["mean_residual_opponent_minus_self"]/total_residual
                if total_residual else None
            ),
            "ready_plus_reachable_share_of_residual":(
                (ready["mean_residual_opponent_minus_self"]+reachable["mean_residual_opponent_minus_self"])
                /total_residual if total_residual else None
            ),
        },
        "asset_type_detail":by_asset_type(raws),
        "cases":[{
            "seed":r["seed"],
            "seat":r["seat"],
            "terminal":r["terminal"],
            "self_summary":r["self"]["summary"],
            "opponent_summary":r["opponent"]["summary"],
        } for r in raws],
        "integrity":integrity,
        "boundary":[
            "READY / REACHABLE / NOT_REACHABLE exactly reconstruct the existing Day20 Committed Production valuation in every side/case.",
            "REACHABLE is reachability only to the public Asset -> Output boundary by terminal, not to terminal Cash.",
            "The reachable share is a valuation decomposition on current displayed-price basis and is not realized profit.",
            "Asset-type detail is retained only for drill-down after the aggregate surface; no product preference or Candidate is inferred."
        ]
    }
    Path("terminal_reachable_asset_surface_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("TERMINAL_REACHABLE_ASSET_SURFACE_RESULT "+json.dumps({
        "terminal_absolute":payload["terminal_absolute"],
        "ready":ready,
        "reachable":reachable,
        "not_reachable":not_reachable,
        "committed":committed,
        "reachable_share":payload["day20_committed_production_decomposition"]["reachable_share_of_opponent_minus_self_committed_residual"],
        "ready_plus_reachable_share":payload["day20_committed_production_decomposition"]["ready_plus_reachable_share_of_residual"],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
