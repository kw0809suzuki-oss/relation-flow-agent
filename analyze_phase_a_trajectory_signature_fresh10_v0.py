#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

src=json.loads(Path("phase_a_trajectory_state_fresh10_v0_aggregate.json").read_text(encoding="utf-8"))

def change_days(days,side,key):
    out=[]
    prev=None
    for d in range(13):
        v=days[str(d)][side][key]
        if prev is not None and v!=prev:
            out.append({"day":d,"from":prev,"to":v,"delta":v-prev})
        prev=v
    return out

def cash_signs(days,side):
    out=[]
    prev=None
    for d in range(13):
        v=days[str(d)][side]["cash"]
        if prev is not None:
            delta=v-prev
            out.append("+" if delta>0 else "-" if delta<0 else "0")
        prev=v
    return out

cases=[]
sig_counts=Counter()
for c in src["cases"]:
    days=c["days"]
    sig={
      "self_unlocked_changes":change_days(days,"self","unlocked_tiles"),
      "self_productive_changes":change_days(days,"self","productive_tiles"),
      "self_worker_changes":change_days(days,"self","workers"),
      "self_cash_delta_signs":cash_signs(days,"self"),
      "opponent_unlocked_changes":change_days(days,"opponent","unlocked_tiles"),
      "opponent_productive_changes":change_days(days,"opponent","productive_tiles"),
      "opponent_worker_changes":change_days(days,"opponent","workers"),
      "opponent_cash_delta_signs":cash_signs(days,"opponent"),
      "productive_gap_sequence":[days[str(d)]["self"]["productive_tiles"]-days[str(d)]["opponent"]["productive_tiles"] for d in range(13)],
    }
    canonical=json.dumps(sig,sort_keys=True,separators=(",",":"))
    sig_counts[canonical]+=1
    cases.append({"seed":c["seed"],"seat":c["seat"],"signature":sig})

payload={
  "schema":"kaggriculture.phase-a-trajectory-signature.fresh10.result.v0",
  "case_count":len(cases),
  "unique_signature_count":len(sig_counts),
  "all_cases_same_signature":len(sig_counts)==1,
  "signature_frequencies":sorted(sig_counts.values(),reverse=True),
  "cases":cases,
  "boundary":[
    "Signature uses only day-by-day external State change points and cash-delta signs.",
    "No terminal label or candidate outcome is used.",
    "A distinct signature establishes only that trajectory representation exposes case-level variation, not that the variation predicts the terminal-best direction."
  ]
}
Path("phase_a_trajectory_signature_fresh10_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("TRAJECTORY_SIGNATURE "+json.dumps({k:payload[k] for k in ("case_count","unique_signature_count","all_cases_same_signature","signature_frequencies")},separators=(",",":")))
