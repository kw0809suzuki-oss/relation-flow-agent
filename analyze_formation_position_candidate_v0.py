#!/usr/bin/env python3
"""Aggregate Formation Position Candidate v0 fixed five-Battle A/B."""
import glob,json
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None

def main():
    paths=sorted(Path(p) for p in glob.glob(
        "formation-position-artifacts/**/formation_position_candidate_v0_*.json",
        recursive=True
    ))
    if len(paths)!=5:
        raise SystemExit(f"Expected 5 artifacts, found {len(paths)}")
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

    bself=[float(r["baseline"]["terminal"]["self"]) for r in raws]
    cself=[float(r["candidate"]["terminal"]["self"]) for r in raws]
    bopp=[float(r["baseline"]["terminal"]["opponent"]) for r in raws]
    copp=[float(r["candidate"]["terminal"]["opponent"]) for r in raws]

    cases=[]
    for r in raws:
        cases.append({
            "seed":r["seed"],
            "seat":r["seat"],
            "baseline_terminal":r["baseline"]["terminal"],
            "candidate_terminal":r["candidate"]["terminal"],
            "terminal_delta":r["terminal_delta"],
            "candidate_telemetry":{
                "modified_turns":r["candidate_telemetry"].get("modified_turns",0),
                "modified_unit_actions":r["candidate_telemetry"].get("modified_unit_actions",0),
                "targets":r["candidate_telemetry"].get("targets",[]),
            },
            "baseline_views":r["baseline"]["views"],
            "candidate_views":r["candidate"]["views"],
        })

    payload={
        "schema":"kaggriculture.strong-origin-v2.formation-position-candidate.result.v0",
        "battle_count":5,
        "baseline_absolute_mean_self":mean(bself),
        "candidate_absolute_mean_self":mean(cself),
        "delta_mean_self":mean([c-b for b,c in zip(bself,cself)]),
        "baseline_absolute_mean_opponent":mean(bopp),
        "candidate_absolute_mean_opponent":mean(copp),
        "baseline_absolute_mean_margin":mean([s-o for s,o in zip(bself,bopp)]),
        "candidate_absolute_mean_margin":mean([s-o for s,o in zip(cself,copp)]),
        "delta_mean_margin":mean([(cs-co)-(bs-bo) for bs,bo,cs,co in zip(bself,bopp,cself,copp)]),
        "improved_cases":sum(c>b for b,c in zip(bself,cself)),
        "worsened_cases":sum(c<b for b,c in zip(bself,cself)),
        "equal_cases":sum(c==b for b,c in zip(bself,cself)),
        "cases":cases,
        "boundary":[
            "This is a terminal Battle A/B result, not a local proxy score.",
            "Candidate only changes Day0 h12 positioning toward distinct adjacent empty tiles; composition remains native.",
            "Local h13/h14 State is retained only to confirm reachability/local behavior change.",
            "Adoption decision must be made from terminal self in relation to the large objective residual."
        ]
    }
    Path("formation_position_candidate_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("FORMATION_POSITION_CANDIDATE_RESULT "+json.dumps({
        "baseline_absolute_mean_self":payload["baseline_absolute_mean_self"],
        "candidate_absolute_mean_self":payload["candidate_absolute_mean_self"],
        "delta_mean_self":payload["delta_mean_self"],
        "baseline_absolute_mean_margin":payload["baseline_absolute_mean_margin"],
        "candidate_absolute_mean_margin":payload["candidate_absolute_mean_margin"],
        "delta_mean_margin":payload["delta_mean_margin"],
        "improved_cases":payload["improved_cases"],
        "worsened_cases":payload["worsened_cases"],
        "equal_cases":payload["equal_cases"],
        "modified_unit_actions":[c["candidate_telemetry"]["modified_unit_actions"] for c in cases],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
