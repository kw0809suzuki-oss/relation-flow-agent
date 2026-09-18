#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent

LAND={(4129,1),(4130,0),(4131,1),(4147,1),(4149,1),(4151,1),(4158,0)}
SEED={(4142,0),(4143,1),(4144,0),(4152,0),(4156,0),(4161,1)}
CASES=sorted(LAND|SEED)
OPP=base.OPPONENT
TURN=108

def snaps(trace):
    return trace["body"]["observe"]["body"]["snapshots"]

def origin_targets_raw(name, day, capacity):
    import strong_origin
    return strong_origin.origin_targets(name, day, capacity)

def play(seed,seat):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    agent.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    def observed(obs): return agent.agent(obs)
    ps=[OPP,OPP]; ps[seat]=observed
    env.run(ps)
    for s in snaps(agent.get_trace()):
        if int(s.get("turn",-1)) != TURN:
            continue
        oi=s.get("origin_internal",{}) or {}
        strategy=oi.get("strategy_name")
        day=int(s.get("day",0) or 0)
        # Capacity is unlocked tile count. Reconstruct from tile signature when explicit value absent.
        capacity=s.get("capacity")
        if capacity is None:
            # current observer already retains target and internal data; use raw target inversion fallback only if explicit capacity missing
            # derive candidate capacity from origin targets by trying plausible farm capacities and matching pre-shift shape later
            capacity_candidates=[]
            for c in range(8,65):
                try:
                    rt=origin_targets_raw(strategy,day,c)
                    capacity_candidates.append((c,rt))
                except Exception:
                    pass
        else:
            capacity_candidates=[(int(capacity),origin_targets_raw(strategy,day,int(capacity)))]

        scores=oi.get("scores",{}) or {}
        best=max(scores,key=scores.get) if scores else None
        distortion=float(oi.get("distortion",0.0) or 0.0)
        cweight=float(oi.get("counter_weight",0.0) or 0.0)
        score_trigger=bool(best is not None and float(scores.get(best,0.0) or 0.0) >= 1.20)
        distortion_trigger=distortion >= 0.10
        counter_trigger=cweight > 0.0

        return {
            "turn":TURN,
            "day":day,
            "strategy_name":strategy,
            "capacity":capacity,
            "capacity_candidates":capacity_candidates,
            "raw_target_candidates":[{"capacity":c,"target":rt} for c,rt in capacity_candidates],
            "distortion":distortion,
            "best_crop":best,
            "best_score":float(scores.get(best,0.0) or 0.0) if best else None,
            "score_trigger":score_trigger,
            "distortion_trigger":distortion_trigger,
            "counter_weight":cweight,
            "counter_trigger":counter_trigger,
            "final_targets":oi.get("targets",{}),
            "market":oi.get("market",[]),
        }
    return None

rows=[]
for seed,seat in CASES:
    rows.append({
        "seed":seed,"seat":seat,
        "group":"land_reinvest" if (seed,seat) in LAND else "seed3",
        "turn108":play(seed,seat)
    })

Path("target_generation_boundary_v1.json").write_text(
    json.dumps({"schema":"target-generation-boundary.v1","policy_mutated":False,"cases":rows},ensure_ascii=False,indent=2)+"\n",
    encoding="utf-8"
)
print("TARGET_GENERATION_BOUNDARY_V1",len(rows))
