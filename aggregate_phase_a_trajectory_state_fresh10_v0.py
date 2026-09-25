#!/usr/bin/env python3
import glob,json
from pathlib import Path
rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("phase-a-trajectory-state-artifacts/**/phase_a_trajectory_state_fresh10_v0_*.json",recursive=True)]
rows=sorted(rows,key=lambda r:r["seed"])
if len(rows)!=10: raise SystemExit(f"Expected 10 cases, got {len(rows)}")
for r in rows:
    missing=[d for d in range(13) if str(d) not in r["days"]]
    if missing: raise SystemExit(f"seed {r['seed']} missing days {missing}")
payload={
  "schema":"kaggriculture.phase-a-trajectory-state.fresh10.aggregate.v0",
  "cases":[{"seed":r["seed"],"seat":r["seat"],"days":r["days"]} for r in rows],
  "sealed_outcome":"No terminal-best direction label is included.",
}
Path("phase_a_trajectory_state_fresh10_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"cases":len(rows)},separators=(",",":")))
