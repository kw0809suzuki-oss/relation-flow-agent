#!/usr/bin/env python3
"""Aggregate Composition Transformation Candidate v0 fixed five-Battle A/B."""
import glob,json
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None

def main():
    paths=sorted(Path(p) for p in glob.glob(
        "composition-candidate-artifacts/**/composition_transformation_candidate_v0_*.json",
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
            "candidate_telemetry":r["candidate_telemetry"],
            "baseline_views":r["baseline"]["views"],
            "candidate_views":r["candidate"]["views"],
        })

    payload={
        "schema":"kaggriculture.strong-origin-v2.composition-transformation-candidate.result.v0",
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
        "replacement_reached_cases":sum(int(r["candidate_telemetry"].get("replaced_actions",0))==1 for r in raws),
        "cases":cases,
        "boundary":[
            "This is the terminal Battle A/B result for a one-unit composition replacement.",
            "The Candidate replaces exactly one native Day0 h14 PLANT WHEAT with PLANT MELON when reachable.",
            "No positioning, timing, movement count, market order, or additional composition change is intentionally introduced.",
            "Local State checkpoints are diagnostic only; adoption is determined by terminal self relative to the parent objective."
        ]
    }
    Path("composition_transformation_candidate_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("COMPOSITION_TRANSFORMATION_CANDIDATE_RESULT "+json.dumps({
        "baseline_absolute_mean_self":payload["baseline_absolute_mean_self"],
        "candidate_absolute_mean_self":payload["candidate_absolute_mean_self"],
        "delta_mean_self":payload["delta_mean_self"],
        "baseline_absolute_mean_margin":payload["baseline_absolute_mean_margin"],
        "candidate_absolute_mean_margin":payload["candidate_absolute_mean_margin"],
        "delta_mean_margin":payload["delta_mean_margin"],
        "improved_cases":payload["improved_cases"],
        "worsened_cases":payload["worsened_cases"],
        "equal_cases":payload["equal_cases"],
        "replacement_reached_cases":payload["replacement_reached_cases"],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
