#!/usr/bin/env python3
"""Aggregate WR-02 Value Carry re-anchor v0 against the prior Body-only surface."""
import glob
import json
import statistics
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

def metric(raws, key):
    selfs=[]; opps=[]; gaps=[]; by_seed={}
    for r in raws:
        seat=int(r["seat"])
        s=float(r["by_player"][str(seat)][key])
        o=float(r["by_player"][str(1-seat)][key])
        g=o-s
        selfs.append(s); opps.append(o); gaps.append(g); by_seed[str(r["seed"])]=g
    return {
        "self_absolute_mean":mean(selfs),
        "opponent_absolute_mean":mean(opps),
        "mean_residual_opponent_minus_self":mean(gaps),
        "median_residual_opponent_minus_self":median(gaps),
        "min_residual":min(gaps),
        "max_residual":max(gaps),
        "opponent_ahead_cases":sum(g>0 for g in gaps),
        "self_ahead_cases":sum(g<0 for g in gaps),
        "equal_cases":sum(g==0 for g in gaps),
        "by_seed":by_seed,
    }

paths=sorted(Path(p) for p in glob.glob(
    "wr02-value-carry-artifacts/**/wr02_production_downstream_boundary_surface_v0_*.json",
    recursive=True
))
if len(paths)!=5:
    raise SystemExit(f"Expected 5 WR-02 artifacts, found {len(paths)}")
raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
old=json.loads(Path("production_downstream_boundary_surface_v0_result.json").read_text(encoding="utf-8"))

committed=metric(raws,"committed_mark_anchor_existing_basis")
reached=metric(raws,"output_reached_mark_same_basis")
harvested=metric(raws,"harvested_mark_same_basis")
not_reached=metric(raws,"not_reached_mark_same_basis")
unharvested=metric(raws,"reached_unharvested_mark_same_basis")

cg=committed["mean_residual_opponent_minus_self"]
rg=reached["mean_residual_opponent_minus_self"]
hg=harvested["mean_residual_opponent_minus_self"]
loss_co=max(0.0,cg-rg)
loss_oh=max(0.0,rg-hg)

term_self=mean([float(r["terminal"]["self"]) for r in raws])
term_opp=mean([float(r["terminal"]["opponent"]) for r in raws])

oldb=old["boundary_surface"]
old_term=old["terminal_absolute"]

payload={
    "schema":"kaggriculture.strong-origin-v2.wr02-value-carry-reanchor.result.v0",
    "active_model":"Baseline+WR-02",
    "battle_count":5,
    "seeds":[7351,7352,7353,7354,7355],
    "anchor":{"day":20,"hour":0,"phase":"pre_market"},
    "terminal_absolute":{
        "mean_self":term_self,
        "mean_opponent":term_opp,
        "mean_margin":term_self-term_opp,
    },
    "boundary_surface":{
        "committed_anchor":committed,
        "output_reached_by_terminal":reached,
        "harvested_from_anchor_assets":harvested,
        "not_reached_by_terminal":not_reached,
        "reached_but_not_harvested":unharvested,
        "residual_retention":{
            "output_reached_over_committed":(rg/cg if cg else None),
            "harvested_over_output_reached":(hg/rg if rg else None),
            "harvested_over_committed":(hg/cg if cg else None),
        },
        "residual_loss":{
            "committed_to_output_reached":loss_co,
            "output_reached_to_harvested":loss_oh,
            "committed_to_harvested":max(0.0,cg-hg),
        },
        "largest_observed_loss_boundary_through_harvest":(
            "committed_to_output_reached" if loss_co>=loss_oh else "output_reached_to_harvested"
        ),
    },
    "comparison_to_prior_body_only":{
        "prior_active_model":"Strong Origin v2 Body-only",
        "prior_committed_residual":float(oldb["committed_anchor"]["mean_residual_opponent_minus_self"]),
        "wr02_committed_residual":cg,
        "committed_residual_delta_wr02_minus_body_only":cg-float(oldb["committed_anchor"]["mean_residual_opponent_minus_self"]),
        "prior_output_reached_residual":float(oldb["output_reached_by_terminal"]["mean_residual_opponent_minus_self"]),
        "wr02_output_reached_residual":rg,
        "prior_harvested_residual":float(oldb["harvested_from_anchor_assets"]["mean_residual_opponent_minus_self"]),
        "wr02_harvested_residual":hg,
        "prior_mean_terminal_self":float(old_term["mean_self"]),
        "wr02_mean_terminal_self":term_self,
        "terminal_self_delta_wr02_minus_body_only":term_self-float(old_term["mean_self"]),
    },
    "cases":[{
        "seed":r["seed"],
        "seat":r["seat"],
        "terminal":r["terminal"],
        "self":{k:v for k,v in r["by_player"][str(r["seat"])].items() if k!="assets"},
        "opponent":{k:v for k,v in r["by_player"][str(1-int(r["seat"]))].items() if k!="assets"},
    } for r in raws],
    "boundary":[
        "This is a re-anchor of the existing fixed-five Day20 cohort surface onto Baseline+WR-02.",
        "Only the same productive assets present at Day20 h0 are followed through actual Output reach and HARVEST.",
        "Marks remain on the Day20 displayed-price basis; they are not realized profit.",
        "The probe still stops at HARVEST/carried. Shed, executable SELL and realized Cash lineage remain open.",
        "No Candidate or adoption decision is introduced."
    ],
}
Path("wr02_value_carry_reanchor_v0_result.json").write_text(
    json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
)
print("WR02_VALUE_CARRY_REANCHOR_RESULT "+json.dumps({
    "terminal_absolute":payload["terminal_absolute"],
    "committed_residual":cg,
    "output_reached_residual":rg,
    "harvested_residual":hg,
    "retention":payload["boundary_surface"]["residual_retention"],
    "loss":payload["boundary_surface"]["residual_loss"],
    "comparison":payload["comparison_to_prior_body_only"],
},ensure_ascii=False,separators=(",",":")))
