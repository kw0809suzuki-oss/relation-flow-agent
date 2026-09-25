#!/usr/bin/env python3
import glob,json
from pathlib import Path

rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("phase-a-external-discriminator-artifacts/**/phase_a_external_discriminator_pair_v0_*.json",recursive=True)]
rows=sorted(rows,key=lambda r:r["seed"])
if [r["seed"] for r in rows] != [8801,8806]:
    raise SystemExit(f"Expected 8801/8806, got {[r['seed'] for r in rows]}")
a,b=rows

def diff(x,y,prefix=""):
    out=[]
    keys=sorted(set((x or {}).keys())|set((y or {}).keys()))
    for k in keys:
        p=f"{prefix}.{k}" if prefix else k
        xv=(x or {}).get(k); yv=(y or {}).get(k)
        if isinstance(xv,dict) and isinstance(yv,dict):
            out.extend(diff(xv,yv,p))
        elif xv!=yv:
            out.append({"field":p,"seed8801":xv,"seed8806":yv})
    return out

daily=[]
first=None
for d in range(13):
    ds=diff(a["days"][str(d)],b["days"][str(d)])
    if ds:
        if first is None:first=d
        daily.append({"day":d,"differences":ds})

first_fields=daily[0]["differences"] if daily else []
first_domains=sorted(set(x["field"].split(".")[0] for x in first_fields))

payload={
  "schema":"kaggriculture.phase-a-external-discriminator-pair.result.v0",
  "pair":[8801,8806],
  "first_observable_difference_day":first,
  "first_difference_domains":first_domains,
  "first_differences":first_fields,
  "daily_differences":daily,
  "boundary":[
    "The pair had identical previously-tested farm trajectory signatures but different terminal-best directions.",
    "This result only locates external observable differences; it does not establish which difference causes the terminal response.",
    "No new representation or policy is promoted by this audit."
  ]
}
Path("phase_a_external_discriminator_pair_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("EXTERNAL_DISCRIMINATOR_PAIR "+json.dumps({
  "first_day":first,
  "domains":first_domains,
  "first_differences":first_fields
},ensure_ascii=False,separators=(",",":")))
