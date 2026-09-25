#!/usr/bin/env python3
"""Aggregate WR-02 Harvest-to-Terminal cohort bounds v0."""
import glob,json
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None

paths=sorted(Path(p) for p in glob.glob(
    "wr02-cohort-bounds-artifacts/**/wr02_harvest_terminal_cohort_bounds_v0_*.json",
    recursive=True
))
if len(paths)!=5:
    raise SystemExit(f"Expected 5 artifacts, found {len(paths)}")
raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

rows=[]
for r in raws:
    seat=int(r["seat"])
    s=r["by_player"][str(seat)]
    o=r["by_player"][str(1-seat)]
    hgap=float(o["cohort_harvested_anchor_mark"])-float(s["cohort_harvested_anchor_mark"])
    slo,shi=map(float,s["cohort_realized_sell_anchor_mark_bound"])
    olo,ohi=map(float,o["cohort_realized_sell_anchor_mark_bound"])
    residual_lo=olo-shi
    residual_hi=ohi-slo
    sclo,schi=map(float,s["cohort_realized_cash_bound"])
    oclo,ochi=map(float,o["cohort_realized_cash_bound"])
    rows.append({
        "seed":r["seed"],"seat":seat,"terminal":r["terminal"],
        "harvested_residual_anchor_mark":hgap,
        "realized_sell_residual_anchor_mark_bound":[residual_lo,residual_hi],
        "realized_cash_residual_bound":[oclo-schi,ochi-sclo],
        "self":s,"opponent":o,
    })

hmean=mean([x["harvested_residual_anchor_mark"] for x in rows])
lo=mean([x["realized_sell_residual_anchor_mark_bound"][0] for x in rows])
hi=mean([x["realized_sell_residual_anchor_mark_bound"][1] for x in rows])
cashlo=mean([x["realized_cash_residual_bound"][0] for x in rows])
cashhi=mean([x["realized_cash_residual_bound"][1] for x in rows])

payload={
    "schema":"kaggriculture.strong-origin-v2.wr02-harvest-terminal-cohort-bounds.result.v0",
    "active_model":"Baseline+WR-02",
    "battle_count":5,
    "mean_surface":{
        "harvested_residual_anchor_mark":hmean,
        "realized_sell_residual_anchor_mark_bound":[lo,hi],
        "realized_sell_residual_retention_bound":[
            (lo/hmean if hmean else None),(hi/hmean if hmean else None)
        ],
        "realized_cash_residual_bound":[cashlo,cashhi],
    },
    "cases":rows,
    "boundary":[
        "Bounds preserve fungibility uncertainty instead of assigning identity to mixed product units.",
        "A wide interval means the current public accounting surface is insufficient to locate Harvest->Sellable->Executable->Realized exactly.",
        "A narrow high-retention interval can close a major-loss hypothesis; a narrow low-retention interval can expose a downstream Value Carry gap.",
        "No Candidate or adoption decision is introduced."
    ],
}
Path("wr02_harvest_terminal_cohort_bounds_v0_result.json").write_text(
    json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
)
print("WR02_HARVEST_TERMINAL_COHORT_BOUNDS_RESULT "+json.dumps(payload["mean_surface"],ensure_ascii=False,separators=(",",":")))
