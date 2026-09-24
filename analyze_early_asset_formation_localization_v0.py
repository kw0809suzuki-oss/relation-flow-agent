#!/usr/bin/env python3
"""Aggregate Early Asset Formation Localization v0."""
import glob
import json
from pathlib import Path

DAYS = tuple(range(0, 9))

def mean(xs):
    return sum(xs) / len(xs) if xs else None

def cp(raw, day):
    for x in raw["checkpoints"]:
        if int(x["day"]) == day:
            return x
    raise KeyError((raw["seed"], day))

def main():
    paths = sorted(Path(p) for p in glob.glob(
        "early-asset-artifacts/**/early_asset_formation_localization_v0_*.json",
        recursive=True,
    ))
    if len(paths) != 5:
        raise SystemExit(f"Expected 5 artifacts, found {len(paths)}")
    raws = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    types = list(cp(raws[0], 0)["self"]["summary_by_type"].keys())

    out_days = {}
    for day in DAYS:
        d = {"land": {}, "assets": {}}
        for field in (
            "unlocked_quadrant_count",
            "unlocked_tile_count",
            "empty_unlocked_tile_count",
            "productive_occupied_tile_count",
        ):
            sv=[float(cp(r,day)["self"]["land"][field]) for r in raws]
            ov=[float(cp(r,day)["opponent"]["land"][field]) for r in raws]
            d["land"][field]={
                "self_absolute_mean":mean(sv),
                "opponent_absolute_mean":mean(ov),
                "mean_residual_opponent_minus_self":mean([o-s for s,o in zip(sv,ov)]),
                "opponent_more_cases":sum(o>s for s,o in zip(sv,ov)),
                "self_more_cases":sum(s>o for s,o in zip(sv,ov)),
            }
        for typ in types:
            d["assets"][typ]={}
            for field in (
                "present_asset_count",
                "held_output_units",
                "current_harvestable_units",
                "near_window_base_units_conditional",
                "future_to_day20_base_units_conditional",
            ):
                sv=[float(cp(r,day)["self"]["summary_by_type"][typ][field]) for r in raws]
                ov=[float(cp(r,day)["opponent"]["summary_by_type"][typ][field]) for r in raws]
                d["assets"][typ][field]={
                    "self_absolute_mean":mean(sv),
                    "opponent_absolute_mean":mean(ov),
                    "mean_residual_opponent_minus_self":mean([o-s for s,o in zip(sv,ov)]),
                    "opponent_more_cases":sum(o>s for s,o in zip(sv,ov)),
                    "self_more_cases":sum(s>o for s,o in zip(sv,ov)),
                }
        out_days[str(day)] = d

    daily_change={}
    for a,b in zip(DAYS[:-1],DAYS[1:]):
        k=f"{a}->{b}"
        daily_change[k]={
            "land":{
                f: out_days[str(b)]["land"][f]["mean_residual_opponent_minus_self"]
                   - out_days[str(a)]["land"][f]["mean_residual_opponent_minus_self"]
                for f in out_days[str(a)]["land"]
            },
            "present_asset":{
                typ: out_days[str(b)]["assets"][typ]["present_asset_count"]["mean_residual_opponent_minus_self"]
                     - out_days[str(a)]["assets"][typ]["present_asset_count"]["mean_residual_opponent_minus_self"]
                for typ in types
            },
            "future_to_day20":{
                typ: out_days[str(b)]["assets"][typ]["future_to_day20_base_units_conditional"]["mean_residual_opponent_minus_self"]
                     - out_days[str(a)]["assets"][typ]["future_to_day20_base_units_conditional"]["mean_residual_opponent_minus_self"]
                for typ in types
            },
        }

    payload={
        "schema":"kaggriculture.strong-origin-v2.early-asset-formation-localization.result.v0",
        "battle_count":5,
        "days":list(DAYS),
        "terminal_absolute":{
            "mean_self":mean([float(r["terminal"]["self"]) for r in raws]),
            "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in raws]),
            "mean_margin":mean([float(r["terminal"]["margin"]) for r in raws]),
        },
        "map_by_day":out_days,
        "daily_residual_changes":daily_change,
        "boundary":[
            "This result localizes only the already-selected Day0->8 coarse interval.",
            "Means and case counts are descriptive World differences, not scores.",
            "No unlike asset types are summed.",
            "No Action, policy, causal explanation, Candidate, or adoption decision is introduced.",
        ],
    }
    Path("early_asset_formation_localization_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    compact={
        "terminal_absolute":payload["terminal_absolute"],
        "days":{
            str(day):{
                "land_tiles":out_days[str(day)]["land"]["unlocked_tile_count"],
                "productive_tiles":out_days[str(day)]["land"]["productive_occupied_tile_count"],
                "present":{
                    typ:out_days[str(day)]["assets"][typ]["present_asset_count"]
                    for typ in types
                },
            } for day in DAYS
        },
        "daily_residual_changes":daily_change,
    }
    print("EARLY_ASSET_FORMATION_LOCALIZATION_RESULT "+json.dumps(
        compact,ensure_ascii=False,separators=(",",":")
    ))

if __name__=="__main__":
    main()
