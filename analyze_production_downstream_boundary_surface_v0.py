#!/usr/bin/env python3
"""Aggregate Production Downstream Boundary Surface v0 fixed-five observations."""
import glob,json,statistics
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

def metric(raws,key):
    sv=[];ov=[]
    for r in raws:
        seat=int(r["seat"])
        sv.append(float(r["by_player"][str(seat)][key]))
        ov.append(float(r["by_player"][str(1-seat)][key]))
    gaps=[o-s for s,o in zip(sv,ov)]
    return {
        "self_absolute_mean":mean(sv),
        "opponent_absolute_mean":mean(ov),
        "mean_residual_opponent_minus_self":mean(gaps),
        "median_residual_opponent_minus_self":median(gaps),
        "min_residual":min(gaps),
        "max_residual":max(gaps),
        "opponent_ahead_cases":sum(x>0 for x in gaps),
        "self_ahead_cases":sum(x<0 for x in gaps),
        "equal_cases":sum(x==0 for x in gaps),
        "by_seed":{str(r["seed"]):g for r,g in zip(raws,gaps)},
    }

def main():
    paths=sorted(Path(p) for p in glob.glob(
        "production-downstream-artifacts/**/production_downstream_boundary_surface_v0_*.json",
        recursive=True
    ))
    if len(paths)!=5:
        raise SystemExit(f"Expected 5 artifacts, found {len(paths)}")
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

    committed=metric(raws,"committed_mark_anchor_existing_basis")
    reached=metric(raws,"output_reached_mark_same_basis")
    harvested=metric(raws,"harvested_mark_same_basis")
    not_reached=metric(raws,"not_reached_mark_same_basis")
    reached_unharvested=metric(raws,"reached_unharvested_mark_same_basis")
    ready=metric(raws,"anchor_ready_mark")

    integrity=[]
    for r in raws:
        seat=int(r["seat"])
        for label,p in (("self",seat),("opponent",1-seat)):
            s=r["by_player"][str(p)]
            e1=float(s["committed_mark_anchor_existing_basis"])-(
                float(s["output_reached_mark_same_basis"])+float(s["not_reached_mark_same_basis"])
            )
            e2=float(s["output_reached_mark_same_basis"])-(
                float(s["harvested_mark_same_basis"])+float(s["reached_unharvested_mark_same_basis"])
            )
            integrity.append({"seed":r["seed"],"side":label,"committed_reconstruction_error":e1,"reached_reconstruction_error":e2})
            if abs(e1)>1e-9 or abs(e2)>1e-9:
                raise SystemExit(f"Integrity mismatch seed={r['seed']} side={label}: {e1}, {e2}")

    cgap=committed["mean_residual_opponent_minus_self"]
    rgap=reached["mean_residual_opponent_minus_self"]
    hgap=harvested["mean_residual_opponent_minus_self"]

    payload={
        "schema":"kaggriculture.strong-origin-v2.production-downstream-boundary-surface.result.v0",
        "battle_count":5,
        "anchor":{"day":20,"hour":0,"phase":"pre_market"},
        "terminal_absolute":{
            "mean_self":mean([float(r["terminal"]["self"]) for r in raws]),
            "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in raws]),
            "mean_margin":mean([float(r["terminal"]["margin"]) for r in raws]),
        },
        "boundary_surface":{
            "committed_anchor":committed,
            "anchor_ready":ready,
            "output_reached_by_terminal":reached,
            "harvested_from_anchor_assets":harvested,
            "not_reached_by_terminal":not_reached,
            "reached_but_not_harvested":reached_unharvested,
            "residual_retention":{
                "output_reached_over_committed":(rgap/cgap if cgap else None),
                "harvested_over_output_reached":(hgap/rgap if rgap else None),
                "harvested_over_committed":(hgap/cgap if cgap else None),
            },
            "residual_change":{
                "committed_to_output_reached":rgap-cgap,
                "output_reached_to_harvested":hgap-rgap,
            },
        },
        "cases":[{
            "seed":r["seed"],"seat":r["seat"],"terminal":r["terminal"],
            "self":{k:v for k,v in r["by_player"][str(r["seat"])].items() if k!="assets"},
            "opponent":{k:v for k,v in r["by_player"][str(1-int(r["seat"]))].items() if k!="assets"},
        } for r in raws],
        "integrity":integrity,
        "boundary":[
            "All marks use the Day20 anchor displayed-price basis and only assets already present at that anchor.",
            "Committed = Output reached + Not reached and Output reached = Harvested + Reached-but-not-harvested exactly for each side/case on this accounting projection.",
            "Passage ratios compare opponent-minus-self residuals across boundaries; they are descriptive residual retention, not causal conversion rates.",
            "Post-anchor bonus output beyond the anchor committed basis is excluded from passage and retained only in raw artifacts.",
            "The surface closes at HARVEST -> carried. No shed, SELL, or Cash lineage is asserted.",
            "No Candidate or adoption decision is introduced."
        ]
    }
    Path("production_downstream_boundary_surface_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("PRODUCTION_DOWNSTREAM_BOUNDARY_SURFACE_RESULT "+json.dumps({
        "terminal_absolute":payload["terminal_absolute"],
        "committed":committed,
        "reached":reached,
        "harvested":harvested,
        "not_reached":not_reached,
        "reached_unharvested":reached_unharvested,
        "retention":payload["boundary_surface"]["residual_retention"],
        "residual_change":payload["boundary_surface"]["residual_change"],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
