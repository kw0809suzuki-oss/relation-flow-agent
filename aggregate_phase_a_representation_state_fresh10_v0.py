#!/usr/bin/env python3
import glob,json
from pathlib import Path

rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("phase-a-representation-state-artifacts/**/phase_a_prompt_state_fresh10_v0_*.json",recursive=True)]
rows=sorted(rows,key=lambda r:r["seed"])
if len(rows)!=10: raise SystemExit(f"Expected 10 states, got {len(rows)}")
payload={
  "schema":"kaggriculture.phase-a-representation-state.fresh10.aggregate.v0",
  "cases":[{"seed":r["seed"],"seat":r["seat"],"checkpoints":r["checkpoints"]} for r in rows],
  "sealed_outcome":"No HOLD / Surface / Throughput / Engine outcome Battle has been run for seeds 8801-8810 at capture time.",
  "next":"Transform these states into neutral cycle representations before committing any direction prediction."
}
Path("phase_a_representation_state_fresh10_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"cases":len(rows)},separators=(",",":")))
