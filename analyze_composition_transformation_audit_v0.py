#!/usr/bin/env python3
"""Aggregate Composition Transformation Audit v0 across fixed five Battles."""
import glob,json
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None

def lane_profile(case,lane):
    return case["lanes"][lane]["new_asset_return_profile_by_type"]

def main():
    paths=sorted(Path(p) for p in glob.glob(
        "composition-transformation-artifacts/**/composition_transformation_audit_v0_*.json",
        recursive=True
    ))
    if len(paths)!=5:
        raise SystemExit(f"Expected 5 artifacts, found {len(paths)}")
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
    lanes=("baseline_self","baseline_seyamalam","position_candidate_self")
    asset_types=sorted(set().union(*[
        set(lane_profile(r,l).keys()) for r in raws for l in lanes
    ]))

    aggregate={}
    for lane in lanes:
        aggregate[lane]={}
        for typ in asset_types:
            qty=[float(lane_profile(r,lane).get(typ,{}).get("quantity",0)) for r in raws]
            first_days=[
                lane_profile(r,lane).get(typ,{}).get("first_return_day")
                for r in raws
                if lane_profile(r,lane).get(typ,{}).get("quantity",0)>0
            ]
            turns=[
                lane_profile(r,lane).get(typ,{}).get("turns_from_h13_entry_to_first_return_boundary")
                for r in raws
                if lane_profile(r,lane).get(typ,{}).get("quantity",0)>0
            ]
            aggregate[lane][typ]={
                "quantity_absolute_mean":mean(qty),
                "present_cases":sum(x>0 for x in qty),
                "first_return_day_values":sorted(set(first_days)),
                "turns_from_h13_values":sorted(set(turns)),
                "quantity_by_seed":{
                    str(r["seed"]):lane_profile(r,lane).get(typ,{}).get("quantity",0)
                    for r in raws
                },
            }

    delta_profiles={}
    for a,b,name in (
        ("baseline_self","baseline_seyamalam","seyamalam_minus_baseline_self"),
        ("baseline_self","position_candidate_self","position_candidate_minus_baseline_self"),
        ("position_candidate_self","baseline_seyamalam","seyamalam_minus_position_candidate"),
    ):
        delta_profiles[name]={}
        for typ in asset_types:
            av=aggregate[a][typ]["quantity_absolute_mean"]
            bv=aggregate[b][typ]["quantity_absolute_mean"]
            delta_profiles[name][typ]=bv-av

    all_boundaries=sorted(set(
        p["first_return_day"]
        for r in raws for l in lanes
        for p in lane_profile(r,l).values()
        if p.get("first_return_day") is not None
    ))
    cumulative={}
    for lane in lanes:
        cumulative[lane]={}
        for d in all_boundaries:
            vals=[]
            by_type={}
            for r in raws:
                total=0
                for typ,p in lane_profile(r,lane).items():
                    if p.get("first_return_day") is not None and p["first_return_day"]<=d:
                        total+=p.get("quantity",0)
                vals.append(float(total))
            cumulative[lane][str(d)]={
                "cumulative_new_asset_count_absolute_mean":mean(vals),
            }
            for typ in asset_types:
                q=[]
                for r in raws:
                    p=lane_profile(r,lane).get(typ,{})
                    q.append(float(p.get("quantity",0) if p.get("first_return_day") is not None and p.get("first_return_day")<=d else 0))
                by_type[typ]=mean(q)
            cumulative[lane][str(d)]["by_type_absolute_mean"]=by_type

    payload={
        "schema":"kaggriculture.strong-origin-v2.composition-transformation-audit.result.v0",
        "battle_count":5,
        "terminal_reference":{
            "baseline_absolute_mean_self":mean([float(r["baseline_terminal"]["self"]) for r in raws]),
            "position_candidate_absolute_mean_self":mean([float(r["position_candidate_terminal"]["self"]) for r in raws]),
            "position_candidate_delta_mean_self":mean([
                float(r["position_candidate_terminal"]["self"])-float(r["baseline_terminal"]["self"])
                for r in raws
            ]),
        },
        "aggregate_new_asset_return_profile":aggregate,
        "quantity_delta_profiles":delta_profiles,
        "cumulative_first_return_profiles":cumulative,
        "cases":[{
            "seed":r["seed"],
            "seat":r["seat"],
            "baseline_self":r["lanes"]["baseline_self"],
            "baseline_seyamalam":r["lanes"]["baseline_seyamalam"],
            "position_candidate_self":r["lanes"]["position_candidate_self"],
        } for r in raws],
        "boundary":[
            "This result is a public-rule timing audit, not a value score.",
            "Unlike asset types remain separate; quantity means are not summed into economic value.",
            "Cumulative first-return counts only locate public maturity boundaries.",
            "No statement is made that reaching a boundary guarantees harvest, sale, cash, or terminal value.",
            "No new Candidate or adoption decision is introduced.",
        ],
    }
    Path("composition_transformation_audit_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("COMPOSITION_TRANSFORMATION_AUDIT_RESULT "+json.dumps({
        "terminal_reference":payload["terminal_reference"],
        "aggregate_new_asset_return_profile":aggregate,
        "quantity_delta_profiles":delta_profiles,
        "cumulative_first_return_profiles":cumulative,
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
