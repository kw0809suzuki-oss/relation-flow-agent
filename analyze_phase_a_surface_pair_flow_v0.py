#!/usr/bin/env python3
import glob, json
from pathlib import Path

rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("phase-a-surface-pair-flow-artifacts/**/phase_a_surface_pair_flow_v0_*.json",recursive=True)]
rows=sorted(rows,key=lambda r:r["seed"])
if [r["seed"] for r in rows] != [8801,8806]:
    raise SystemExit(f"Expected 8801/8806, got {[r['seed'] for r in rows]}")

def diff(x,y,prefix=""):
    out=[]
    keys=sorted(set((x or {}).keys())|set((y or {}).keys()))
    for k in keys:
        p=f"{prefix}.{k}" if prefix else k
        xv=(x or {}).get(k); yv=(y or {}).get(k)
        if isinstance(xv,dict) and isinstance(yv,dict):
            out.extend(diff(xv,yv,p))
        elif xv!=yv:
            out.append({"field":p,"active":xv,"surface":yv})
    return out

cases=[]
for r in rows:
    first=None; daily=[]
    for d in range(13):
        a=r["active"]["daily"].get(str(d),{})
        s=r["surface"]["daily"].get(str(d),{})
        ds=diff(a,s)
        if ds:
            if first is None:first=d
            daily.append({"day":d,"differences":ds})
    cases.append({
      "seed":r["seed"],
      "delta_terminal_self":r["delta_terminal_self"],
      "first_active_surface_difference_day":first,
      "surface_changed_turns":r["surface"]["telemetry"].get("changed_turns"),
      "daily_differences":daily,
    })

payload={
  "schema":"kaggriculture.phase-a-surface-pair-flow.result.v0",
  "cases":cases,
  "boundary":[
    "This result compares Active WR-02 with Surface First within each seed.",
    "It locates the first observed downstream state difference caused by the candidate path.",
    "Cross-seed shop/market differences remain separate evidence; no causal bridge is asserted without overlap."
  ]
}
Path("phase_a_surface_pair_flow_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"cases":[{"seed":c["seed"],"delta":c["delta_terminal_self"],"first_day":c["first_active_surface_difference_day"],"changed_turns":c["surface_changed_turns"]} for c in cases]},ensure_ascii=False))
