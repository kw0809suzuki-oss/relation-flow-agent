#!/usr/bin/env python3
import glob,json
from pathlib import Path

blind_rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("blind/**/shadow_interview_blind_*.json",recursive=True)]
sealed_rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("sealed/**/shadow_interview_sealed_*.json",recursive=True)]

samples=[]
for r in sorted(blind_rows,key=lambda x:x["seed"]):
    samples.extend(r.get("samples",[]))

picked=[]; counts={}
for s in samples:
    crit=s["sampling_criterion"]
    if counts.get(crit,0)>=2: continue
    counts[crit]=counts.get(crit,0)+1
    picked.append(s)

blind_out={
 "schema":"kaggriculture.shadow-interview.blind.aggregate.v1",
 "cases":len(blind_rows),
 "interview_set":picked,
 "sample_counts_by_criterion":counts,
 "instruction":"Interview using only this artifact. Do not access sealed actuals until responses are frozen."
}
Path("shadow_interview_blind_aggregate_v1.json").write_text(json.dumps(blind_out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

sealed={}
for r in sealed_rows:
    for a in r.get("actuals",[]): sealed[a["sample_id"]]=a
sealed_out={"schema":"kaggriculture.shadow-interview.sealed.aggregate.v1","actuals":sealed}
Path("shadow_interview_sealed_aggregate_v1.json").write_text(json.dumps(sealed_out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"blind_cases":len(blind_rows),"interview_samples":len(picked),"criteria":counts,"sealed_actuals":len(sealed)},ensure_ascii=False))
