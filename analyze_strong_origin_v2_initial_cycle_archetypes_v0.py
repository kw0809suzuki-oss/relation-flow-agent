#!/usr/bin/env python3
"""Aggregate Strong Origin v2 initial-cycle archetypes fresh batch."""
import glob
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

MODES=("FAST_CLOSURE","PRODUCTIVE_OCCUPANCY","CAPITAL_PRESERVATION","ANIMAL_CYCLE")


def mean(xs): return sum(xs)/len(xs) if xs else None

def median(xs): return statistics.median(xs) if xs else None


def closure_summary(rows,side="self"):
    cs=[r["closure"][side] for r in rows]
    closed=[c for c in cs if c.get("closed")]
    turns=[float(c["turn"]) for c in closed if c.get("turn") is not None]
    assets=[float(c["productive_assets_at_closure"]) for c in closed if c.get("productive_assets_at_closure") is not None]
    cash=[float(c["generated_sell_cash_to_closure"]) for c in closed]
    reinvest=Counter(c.get("reinvestment_op") for c in closed if c.get("reinvestment_op"))
    sources=Counter(c.get("source_item") for c in closed if c.get("source_item"))
    confidence=Counter(c.get("lineage_confidence") for c in closed if c.get("lineage_confidence"))
    return {
        "closure_rate":len(closed)/len(cs) if cs else None,
        "closed_cases":len(closed),
        "mean_closure_turn":mean(turns),
        "median_closure_turn":median(turns),
        "mean_closure_day_equivalent":mean(turns)/24.0 if turns else None,
        "mean_productive_assets_at_closure":mean(assets),
        "mean_generated_sell_cash_to_closure":mean(cash),
        "reinvestment_op_counts":dict(reinvest),
        "source_item_counts":dict(sources),
        "lineage_confidence_counts":dict(confidence),
    }


def snapshot_metric(rows,day,key):
    vals=[r["snapshots"][str(day)]["self"][key] for r in rows if r["snapshots"].get(str(day)) and r["snapshots"][str(day)].get("self")]
    return mean([float(x) for x in vals]) if vals else None


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/strong_origin_v2_initial_cycle_archetypes_v0_*.json"))
    if not files:
        files=[Path(p) for p in glob.glob(str(root/"**"/"strong_origin_v2_initial_cycle_archetypes_v0_*.json"),recursive=True)]
    if not files:
        raise SystemExit("No initial-cycle archetype files")

    cases=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    cases.sort(key=lambda x:int(x["seed"]))

    body_rows=[c["results"]["BODY_ONLY"] for c in cases]
    baseline_self=[float(r["terminal"]["self"]) for r in body_rows]
    baseline_opp=[float(r["terminal"]["opponent"]) for r in body_rows]
    baseline_margin=[float(r["terminal"]["margin"]) for r in body_rows]

    baseline={
        "absolute_mean_self":mean(baseline_self),
        "absolute_mean_opponent":mean(baseline_opp),
        "mean_margin":mean(baseline_margin),
        "wins":sum(bool(r["terminal"]["win"]) for r in body_rows),
        "closure":closure_summary(body_rows),
        "day4":{
            "productive_assets_mean":snapshot_metric(body_rows,4,"productive_assets"),
            "committed_production_potential_mark_mean":snapshot_metric(body_rows,4,"committed_production_potential_mark"),
            "empty_unlocked_tiles_mean":snapshot_metric(body_rows,4,"empty_unlocked_tiles"),
            "cash_mean":snapshot_metric(body_rows,4,"cash"),
        },
    }

    bundles={}
    for mode in MODES:
        rows=[c["results"][mode] for c in cases]
        self_vals=[float(r["terminal"]["self"]) for r in rows]
        opp_vals=[float(r["terminal"]["opponent"]) for r in rows]
        margins=[float(r["terminal"]["margin"]) for r in rows]
        deltas=[s-b for s,b in zip(self_vals,baseline_self)]
        margin_deltas=[m-b for m,b in zip(margins,baseline_margin)]
        paired_closure_delta=[]
        for r,b in zip(rows,body_rows):
            ct=r["closure"]["self"].get("turn")
            bt=b["closure"]["self"].get("turn")
            if ct is not None and bt is not None:
                paired_closure_delta.append(float(ct)-float(bt))
        bundles[mode]={
            "baseline_absolute_mean_self":baseline["absolute_mean_self"],
            "candidate_absolute_mean_self":mean(self_vals),
            "delta_mean_self":mean(deltas),
            "candidate_absolute_mean_opponent":mean(opp_vals),
            "candidate_mean_margin":mean(margins),
            "delta_mean_margin":mean(margin_deltas),
            "candidate_wins":sum(bool(r["terminal"]["win"]) for r in rows),
            "self_improved":sum(x>0 for x in deltas),
            "self_worsened":sum(x<0 for x in deltas),
            "self_equal":sum(x==0 for x in deltas),
            "closure":closure_summary(rows),
            "mean_paired_closure_turn_delta_vs_body":mean(paired_closure_delta),
            "day4":{
                "productive_assets_mean":snapshot_metric(rows,4,"productive_assets"),
                "committed_production_potential_mark_mean":snapshot_metric(rows,4,"committed_production_potential_mark"),
                "empty_unlocked_tiles_mean":snapshot_metric(rows,4,"empty_unlocked_tiles"),
                "cash_mean":snapshot_metric(rows,4,"cash"),
            },
        }

    payload={
        "schema":"kaggriculture.strong-origin-v2.initial-cycle-archetypes.aggregate.v0",
        "battle_count":len(cases),
        "baseline":baseline,
        "bundles":bundles,
        "cases":cases,
        "boundary":[
            "Compare whole economic outcomes before interpreting local differences.",
            "Every bundle preserves baseline absolute mean self, candidate absolute mean self, and delta.",
            "Closure speed is not an adoption criterion by itself.",
            "Day4 state quality and terminal self remain separate observations.",
            "WHEAT lineage ambiguity is retained explicitly rather than treated as confirmed provenance.",
            "No overall winner or adoption decision is emitted by this aggregate."
        ]
    }
    Path("strong_origin_v2_initial_cycle_archetypes_v0_aggregate.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("INITIAL_CYCLE_ARCHETYPES_AGG "+json.dumps({
        "battle_count":len(cases),
        "baseline":baseline,
        "bundles":bundles,
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
