#!/usr/bin/env python3
"""Aggregate h13 Formation Feasibility Surface v0."""
import glob, json
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None

def summarize_scalar(cases, path):
    sv=[]; ov=[]
    for c in cases:
        s=c["self"]; o=c["opponent"]
        for p in path:
            s=s[p]; o=o[p]
        sv.append(float(s)); ov.append(float(o))
    return {
        "self_absolute_mean":mean(sv),
        "opponent_absolute_mean":mean(ov),
        "mean_residual_opponent_minus_self":mean([o-s for s,o in zip(sv,ov)]),
        "opponent_more_cases":sum(o>s for s,o in zip(sv,ov)),
        "self_more_cases":sum(s>o for s,o in zip(sv,ov)),
        "equal_cases":sum(s==o for s,o in zip(sv,ov)),
    }

def summarize_map(cases, key):
    names=sorted(set().union(*[
        set(c["self"]["h13_resources"][key].keys()) |
        set(c["opponent"]["h13_resources"][key].keys())
        for c in cases
    ]))
    out={}
    for name in names:
        sv=[float(c["self"]["h13_resources"][key].get(name,0)) for c in cases]
        ov=[float(c["opponent"]["h13_resources"][key].get(name,0)) for c in cases]
        out[name]={
            "self_absolute_mean":mean(sv),
            "opponent_absolute_mean":mean(ov),
            "mean_residual_opponent_minus_self":mean([o-s for s,o in zip(sv,ov)]),
            "opponent_more_cases":sum(o>s for s,o in zip(sv,ov)),
            "self_more_cases":sum(s>o for s,o in zip(sv,ov)),
            "equal_cases":sum(s==o for s,o in zip(sv,ov)),
        }
    return out

def main():
    paths=sorted(Path(p) for p in glob.glob(
        "h13-feasibility-artifacts/**/h13_formation_feasibility_v0_*.json",
        recursive=True
    ))
    if len(paths)!=5:
        raise SystemExit(f"Expected 5 artifacts, found {len(paths)}")
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

    resource_fields=[
        "money","empty_unlocked_tile_count","unlocked_tile_count",
        "productive_occupied_tile_count","hands_count","acting_unit_count",
        "private_inventory_slot_count","units_on_empty_tile_count"
    ]
    resources={f:summarize_scalar(raws,["h13_resources",f]) for f in resource_fields}
    seed_stock=summarize_map(raws,"seed_stock")
    animal_stock=summarize_map(raws,"unplaced_animal_stock")

    asset_types=sorted(set().union(*[
        set(r["self"]["h13_to_h14_present_asset_delta"].keys()) |
        set(r["opponent"]["h13_to_h14_present_asset_delta"].keys())
        for r in raws
    ]))
    delta={}
    for typ in asset_types:
        sv=[float(r["self"]["h13_to_h14_present_asset_delta"].get(typ,0)) for r in raws]
        ov=[float(r["opponent"]["h13_to_h14_present_asset_delta"].get(typ,0)) for r in raws]
        delta[typ]={
            "self_absolute_mean":mean(sv),
            "opponent_absolute_mean":mean(ov),
            "mean_residual_opponent_minus_self":mean([o-s for s,o in zip(sv,ov)]),
            "opponent_more_cases":sum(o>s for s,o in zip(sv,ov)),
            "self_more_cases":sum(s>o for s,o in zip(sv,ov)),
            "equal_cases":sum(s==o for s,o in zip(sv,ov)),
        }

    cases=[]
    for r in raws:
        cases.append({
            "seed":r["seed"],"seat":r["seat"],"terminal":r["terminal"],
            "self_h13_resources":r["self"]["h13_resources"],
            "opponent_h13_resources":r["opponent"]["h13_resources"],
            "self_h13_to_h14_delta":r["self"]["h13_to_h14_present_asset_delta"],
            "opponent_h13_to_h14_delta":r["opponent"]["h13_to_h14_present_asset_delta"],
            "material_reference":r["material_reference"],
        })

    payload={
        "schema":"kaggriculture.strong-origin-v2.h13-formation-feasibility.result.v0",
        "battle_count":5,
        "terminal_absolute":{
            "mean_self":mean([float(r["terminal"]["self"]) for r in raws]),
            "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in raws]),
            "mean_margin":mean([float(r["terminal"]["margin"]) for r in raws]),
        },
        "h13_resources":resources,
        "h13_seed_stock":seed_stock,
        "h13_unplaced_animal_stock":animal_stock,
        "h13_to_h14_present_asset_delta":delta,
        "cases":cases,
        "boundary":[
            "Resource fields are h13 World-state facts only.",
            "Seed/animal stock are immediate material stock; money is separate acquisition capacity.",
            "units_on_empty_tile_count is positional surface only and is not legal reachability proof.",
            "No Action, policy, motive, Candidate, or causal explanation is inferred."
        ]
    }
    Path("h13_formation_feasibility_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("H13_FORMATION_FEASIBILITY_RESULT "+json.dumps({
        "terminal_absolute":payload["terminal_absolute"],
        "resources":resources,
        "seed_stock":seed_stock,
        "animal_stock":animal_stock,
        "delta":delta
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
