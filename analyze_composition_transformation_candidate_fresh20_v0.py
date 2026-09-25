#!/usr/bin/env python3
"""Fresh20 independent Battle validation for Composition Transformation Candidate v0."""
import glob,json,statistics
from pathlib import Path

EXPECTED=20

def mean(xs): return sum(xs)/len(xs) if xs else None

def main():
    paths=sorted(Path(p) for p in glob.glob(
        "composition-fresh20-artifacts/**/composition_transformation_candidate_v0_*.json",
        recursive=True
    ))
    if len(paths)!=EXPECTED:
        raise SystemExit(f"Expected {EXPECTED} artifacts, found {len(paths)}")
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

    bself=[float(r["baseline"]["terminal"]["self"]) for r in raws]
    cself=[float(r["candidate"]["terminal"]["self"]) for r in raws]
    bopp=[float(r["baseline"]["terminal"]["opponent"]) for r in raws]
    copp=[float(r["candidate"]["terminal"]["opponent"]) for r in raws]
    dself=[c-b for b,c in zip(bself,cself)]
    dmargin=[(cs-co)-(bs-bo) for bs,bo,cs,co in zip(bself,bopp,cself,copp)]

    cases=[]
    for r in raws:
        cases.append({
            "seed":int(r["seed"]),
            "seat":int(r["seat"]),
            "baseline_self":float(r["baseline"]["terminal"]["self"]),
            "candidate_self":float(r["candidate"]["terminal"]["self"]),
            "delta_self":float(r["terminal_delta"]["self"]),
            "baseline_margin":float(r["baseline"]["terminal"]["margin"]),
            "candidate_margin":float(r["candidate"]["terminal"]["margin"]),
            "delta_margin":float(r["terminal_delta"]["margin"]),
            "replacement_reached":int(r["candidate_telemetry"].get("replaced_actions",0))==1,
        })

    payload={
        "schema":"kaggriculture.strong-origin-v2.composition-transformation-candidate.fresh20.validation.v0",
        "battle_count":EXPECTED,
        "seed_range":[min(c["seed"] for c in cases),max(c["seed"] for c in cases)],
        "baseline_absolute_mean_self":mean(bself),
        "candidate_absolute_mean_self":mean(cself),
        "delta_mean_self":mean(dself),
        "delta_median_self":statistics.median(dself),
        "delta_min_self":min(dself),
        "delta_max_self":max(dself),
        "baseline_absolute_mean_margin":mean([s-o for s,o in zip(bself,bopp)]),
        "candidate_absolute_mean_margin":mean([s-o for s,o in zip(cself,copp)]),
        "delta_mean_margin":mean(dmargin),
        "improved_cases":sum(x>0 for x in dself),
        "worsened_cases":sum(x<0 for x in dself),
        "equal_cases":sum(x==0 for x in dself),
        "replacement_reached_cases":sum(c["replacement_reached"] for c in cases),
        "cases":sorted(cases,key=lambda x:x["seed"]),
        "boundary":[
            "This is independent fresh20 terminal Battle validation.",
            "Candidate implementation is unchanged from the fixed-five Battle.",
            "No new interpretation, threshold, rescue rule, or local optimization is introduced.",
            "Primary adoption evidence is baseline absolute mean self, candidate absolute mean self, delta, and the per-case distribution."
        ]
    }
    Path("composition_transformation_candidate_fresh20_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("COMPOSITION_TRANSFORMATION_FRESH20_RESULT "+json.dumps({
        "battle_count":payload["battle_count"],
        "seed_range":payload["seed_range"],
        "baseline_absolute_mean_self":payload["baseline_absolute_mean_self"],
        "candidate_absolute_mean_self":payload["candidate_absolute_mean_self"],
        "delta_mean_self":payload["delta_mean_self"],
        "delta_median_self":payload["delta_median_self"],
        "delta_min_self":payload["delta_min_self"],
        "delta_max_self":payload["delta_max_self"],
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
