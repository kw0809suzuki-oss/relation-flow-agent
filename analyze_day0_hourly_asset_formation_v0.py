#!/usr/bin/env python3
"""Aggregate Day0 Hourly Asset Formation Localization v0."""
import glob
import json
from pathlib import Path

def mean(xs):
    return sum(xs)/len(xs) if xs else None

def key(c):
    return f"{int(c['day'])}:{int(c['hour']):02d}"

def main():
    paths=sorted(Path(p) for p in glob.glob(
        "day0-hourly-artifacts/**/day0_hourly_asset_formation_v0_*.json",
        recursive=True,
    ))
    if len(paths)!=5:
        raise SystemExit(f"Expected 5 artifacts, found {len(paths)}")
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
    keys=[key(c) for c in raws[0]["checkpoints"]]
    types=list(raws[0]["checkpoints"][0]["self"]["summary_by_type"].keys())

    by_time={}
    for k in keys:
        cs=[]
        for r in raws:
            c=next(x for x in r["checkpoints"] if key(x)==k)
            cs.append(c)
        entry={"land":{},"present":{}}
        for f in ("unlocked_tile_count","empty_unlocked_tile_count","productive_occupied_tile_count"):
            sv=[float(c["self"]["land"][f]) for c in cs]
            ov=[float(c["opponent"]["land"][f]) for c in cs]
            entry["land"][f]={
                "self_absolute_mean":mean(sv),
                "opponent_absolute_mean":mean(ov),
                "mean_residual_opponent_minus_self":mean([o-s for s,o in zip(sv,ov)]),
                "opponent_more_cases":sum(o>s for s,o in zip(sv,ov)),
                "self_more_cases":sum(s>o for s,o in zip(sv,ov)),
            }
        for typ in types:
            sv=[float(c["self"]["summary_by_type"][typ]["present_asset_count"]) for c in cs]
            ov=[float(c["opponent"]["summary_by_type"][typ]["present_asset_count"]) for c in cs]
            entry["present"][typ]={
                "self_absolute_mean":mean(sv),
                "opponent_absolute_mean":mean(ov),
                "mean_residual_opponent_minus_self":mean([o-s for s,o in zip(sv,ov)]),
                "opponent_more_cases":sum(o>s for s,o in zip(sv,ov)),
                "self_more_cases":sum(s>o for s,o in zip(sv,ov)),
            }
        by_time[k]=entry

    first_productive_5of5=None
    first_nonzero_mean=None
    for k in keys:
        p=by_time[k]["land"]["productive_occupied_tile_count"]
        if first_nonzero_mean is None and p["mean_residual_opponent_minus_self"] != 0:
            first_nonzero_mean=k
        if first_productive_5of5 is None and p["opponent_more_cases"]==5:
            first_productive_5of5=k

    payload={
        "schema":"kaggriculture.strong-origin-v2.day0-hourly-asset-formation.result.v0",
        "battle_count":5,
        "terminal_absolute":{
            "mean_self":mean([float(r["terminal"]["self"]) for r in raws]),
            "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in raws]),
            "mean_margin":mean([float(r["terminal"]["margin"]) for r in raws]),
        },
        "first_nonzero_mean_productive_residual":first_nonzero_mean,
        "first_opponent_more_productive_5_of_5":first_productive_5of5,
        "map_by_time":by_time,
        "boundary":[
            "The first-time markers refer only to productive occupied World tiles.",
            "No Action or causal mechanism is inferred from the timing marker.",
            "Unlike asset types remain separate and are not value-weighted.",
            "No Candidate or adoption decision is introduced.",
        ],
    }
    Path("day0_hourly_asset_formation_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("DAY0_HOURLY_ASSET_FORMATION_RESULT "+json.dumps({
        "terminal_absolute":payload["terminal_absolute"],
        "first_nonzero_mean":first_nonzero_mean,
        "first_5of5":first_productive_5of5,
        "times":{
            k:{
                "productive":v["land"]["productive_occupied_tile_count"],
                "present":v["present"],
            } for k,v in by_time.items()
        },
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
