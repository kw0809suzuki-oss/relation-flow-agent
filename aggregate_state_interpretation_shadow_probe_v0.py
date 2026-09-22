#!/usr/bin/env python3
import glob,json
from pathlib import Path
rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("artifacts/**/state_interpretation_shadow_probe_v0_*.json",recursive=True)]
samples=[]
for r in sorted(rows,key=lambda x:x["seed"]):
    samples.extend(r.get("samples",[]))
# Thin global interview set: keep two per mechanical criterion at most.
picked=[]; counts={}
for s in samples:
    crit=s["sampling_criterion"]
    if counts.get(crit,0)>=2: continue
    counts[crit]=counts.get(crit,0)+1
    picked.append(s)
payload={
  "schema":"kaggriculture.state-interpretation-shadow-probe.aggregate.v0",
  "cases":len(rows),
  "interview_set":picked,
  "sample_counts_by_criterion":counts,
  "actual_choice_visibility":"sealed_inside_each_sample; interviewer should read only interview_input before answering",
  "next":"Run independent model interview on interview_input, then unseal actual choice for divergence analysis."
}
Path("state_interpretation_shadow_probe_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"cases":len(rows),"interview_samples":len(picked),"counts":counts},ensure_ascii=False))
