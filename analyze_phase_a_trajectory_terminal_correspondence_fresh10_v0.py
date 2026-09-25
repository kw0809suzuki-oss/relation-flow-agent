#!/usr/bin/env python3
import glob, hashlib, json
from collections import defaultdict, Counter
from pathlib import Path

traj=json.loads(Path("phase_a_trajectory_signature_fresh10_v0_result.json").read_text(encoding="utf-8"))
paths=sorted(Path(p) for p in glob.glob("phase-a-trajectory-outcome-artifacts/**/phase_a_takeoff_fresh20_v0_*.json",recursive=True))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
if len(rows)!=10: raise SystemExit(f"Expected 10 outcome cases, got {len(rows)}")

def terminals(r):
    return {
      "hold":float(r["active_wr02"]["terminal"]["self"]),
      "surface_first":float(r["candidates"]["surface_first"]["terminal"]["self"]),
      "throughput_first":float(r["candidates"]["throughput_first"]["terminal"]["self"]),
      "engine_first":float(r["candidates"]["engine_first"]["terminal"]["self"]),
    }

outcome={}
for r in rows:
    vals=terminals(r)
    best=max(vals.values())
    outcome[int(r["seed"])]={
      "terminal_self":vals,
      "oracle_best_self":best,
      "winners":sorted(k for k,v in vals.items() if v==best),
    }

groups=defaultdict(list)
cases=[]
for c in traj["cases"]:
    seed=int(c["seed"])
    sig=c["signature"]
    canonical=json.dumps(sig,sort_keys=True,separators=(",",":"))
    sig_hash=hashlib.sha256(canonical.encode()).hexdigest()
    item={"seed":seed,"signature_hash":sig_hash,**outcome[seed]}
    cases.append(item)
    groups[sig_hash].append(item)

duplicate_groups=[]
same_signature_different_winner=False
for h,items in groups.items():
    if len(items)<2: continue
    winner_sets=[tuple(x["winners"]) for x in items]
    consistent=len(set(winner_sets))==1
    if not consistent:
        same_signature_different_winner=True
    duplicate_groups.append({
      "signature_hash":h,
      "seeds":[x["seed"] for x in items],
      "winner_sets":[x["winners"] for x in items],
      "consistent_terminal_best_direction":consistent,
    })

winner_counts=Counter(w for c in cases for w in c["winners"])
hold_mean=sum(c["terminal_self"]["hold"] for c in cases)/len(cases)
oracle_mean=sum(c["oracle_best_self"] for c in cases)/len(cases)

if same_signature_different_winner:
    mechanical_result="trajectory_signature_insufficient"
elif duplicate_groups:
    mechanical_result="not_falsified_but_correspondence_not_established"
else:
    mechanical_result="no_repeated_signature_test_available"

payload={
  "schema":"kaggriculture.phase-a-trajectory-terminal-correspondence.fresh10.result.v0",
  "battle_count":len(cases),
  "hold_absolute_mean_self":hold_mean,
  "oracle_absolute_mean_self":oracle_mean,
  "oracle_delta_vs_hold":oracle_mean-hold_mean,
  "winner_counts":dict(winner_counts),
  "trajectory_unique_signature_count":traj["unique_signature_count"],
  "duplicate_signature_groups":duplicate_groups,
  "same_trajectory_signature_different_terminal_best_direction":same_signature_different_winner,
  "mechanical_result":mechanical_result,
  "cases":sorted(cases,key=lambda x:x["seed"]),
  "boundary":[
    "Trajectory signatures were fixed before candidate outcome Battles were opened.",
    "This test asks only whether identical trajectory signatures can map to different terminal-best directions.",
    "If an identical signature has different winners, the tested signature is mechanically insufficient.",
    "If no contradiction is observed, correspondence is not automatically established."
  ]
}
Path("phase_a_trajectory_terminal_correspondence_fresh10_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("TRAJECTORY_TERMINAL_CORRESPONDENCE "+json.dumps({
  "hold_mean":hold_mean,
  "oracle_mean":oracle_mean,
  "oracle_delta_vs_hold":oracle_mean-hold_mean,
  "winner_counts":dict(winner_counts),
  "duplicate_signature_groups":duplicate_groups,
  "same_signature_different_winner":same_signature_different_winner,
  "mechanical_result":mechanical_result
},ensure_ascii=False,separators=(",",":")))
