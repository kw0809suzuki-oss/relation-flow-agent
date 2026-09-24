#!/usr/bin/env python3
"""Aggregate Harvestable STRAWBERRY Gate v0."""
import glob, json
from pathlib import Path

def mean(xs):
    return sum(xs)/len(xs) if xs else None

def main():
    paths = sorted(Path(p) for p in glob.glob(
        "harvestable-strawberry-artifacts/**/harvestable_strawberry_gate_v0_*.json",
        recursive=True,
    ))
    if len(paths) != 5:
        raise SystemExit(f"Expected 5 artifacts, found {len(paths)}")
    raws = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    cases=[]
    for r in raws:
        seat=int(r["seat"])
        s=r["by_player"][str(seat)] if isinstance(r["by_player"], dict) and str(seat) in r["by_player"] else r["by_player"][seat]
        oidx=1-seat
        o=r["by_player"][str(oidx)] if isinstance(r["by_player"], dict) and str(oidx) in r["by_player"] else r["by_player"][oidx]
        cases.append({
            "seed":r["seed"],
            "seat":seat,
            "terminal":r["terminal"],
            "self":s,
            "opponent":o,
        })

    fields=[
        "day20_h0_harvestable_stock",
        "refresh_added_available_before_day24",
        "harvestable_supply_available_in_window",
        "harvest_to_carried_units",
        "refresh_harvestable_losses_inside_window",
        "other_harvestable_losses_inside_window",
        "day24_h0_endpoint_refresh_addition_excluded",
        "max_turn_start_harvestable_stock",
        "mean_turn_start_harvestable_stock",
    ]
    means={}
    for f in fields:
        sv=[float(c["self"][f] or 0) for c in cases]
        ov=[float(c["opponent"][f] or 0) for c in cases]
        means[f]={
            "self_absolute_mean":mean(sv),
            "opponent_absolute_mean":mean(ov),
            "mean_residual_opponent_minus_self":mean([o-s for s,o in zip(sv,ov)]),
        }

    for c in cases:
        ss=float(c["self"]["harvestable_supply_available_in_window"] or 0)
        os=float(c["opponent"]["harvestable_supply_available_in_window"] or 0)
        sh=float(c["self"]["harvest_to_carried_units"] or 0)
        oh=float(c["opponent"]["harvest_to_carried_units"] or 0)
        c["self"]["harvest_fraction_of_observed_supply"] = sh/ss if ss>0 else None
        c["opponent"]["harvest_fraction_of_observed_supply"] = oh/os if os>0 else None

    payload={
        "schema":"kaggriculture.strong-origin-v2.harvestable-strawberry-gate.result.v0",
        "battle_count":5,
        "terminal_absolute":{
            "mean_self":mean([float(c["terminal"]["self"]) for c in cases]),
            "mean_opponent":mean([float(c["terminal"]["opponent"]) for c in cases]),
            "mean_margin":mean([float(c["terminal"]["margin"]) for c in cases]),
        },
        "means":means,
        "cases":cases,
        "boundary":[
            "Absolute means are reported for World-side harvestable STRAWBERRY supply and exact HARVEST->carried units.",
            "harvest_fraction_of_observed_supply is descriptive only; it is not an efficiency score or policy judgment.",
            "Supply is not a time-sum of stock snapshots; it is starting harvestable stock plus public daily-refresh additions that became available before Day24.",
            "No cause for unharvested supply and no Candidate are inferred.",
        ],
    }
    Path("harvestable_strawberry_gate_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("HARVESTABLE_STRAWBERRY_GATE_RESULT "+json.dumps({
        "terminal_absolute":payload["terminal_absolute"],
        "means":payload["means"],
        "cases":[
            {
                "seed":c["seed"],
                "self_supply":c["self"]["harvestable_supply_available_in_window"],
                "self_harvest":c["self"]["harvest_to_carried_units"],
                "opponent_supply":c["opponent"]["harvestable_supply_available_in_window"],
                "opponent_harvest":c["opponent"]["harvest_to_carried_units"],
            } for c in cases
        ],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
