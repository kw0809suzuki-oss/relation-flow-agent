#!/usr/bin/env python3
"""WR-01 World Transformation Audit v0.

Compare baseline vs unchanged WR-01 on fixed five Battles.
Question:
Do WR-01's reopened terminal-reachable productive purchases actually appear
as additional productive World State, or mostly remain as purchased inventory?

Observation checkpoints: Day14/16/20/24 h0 before the agent action.
"""
import json,os
from pathlib import Path
from kaggle_environments import make

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as baseline
import world_reference_reachability_candidate_v0 as wr01

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"wr01_world_transformation_audit_v0_{SEED}_seat{SEAT}.json")
CHECK={(14,0),(16,0),(20,0),(24,0)}


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"


def view(obs):
    d=econ.derive_side(obs)
    p=int(obs["player"])
    farm=obs["farms"][p]
    return {
        "cash":float(d["cash"]),
        "seed_inventory":dict(d["seed_inventory_fact"]),
        "crop_count":dict(d["committed_production"]["crop_count"]),
        "animal_count":dict(d["committed_production"]["animal_count"]),
        "committed_mark":float(d["committed_production"]["same_basis_subtotal"]),
        "crop_mark":float(d["committed_production"]["crop_current_price_potential_mark"]),
        "animal_mark":float(d["committed_production"]["animal_base_current_price_potential_mark"]),
        "unlocked_tiles":int(d["uncommitted_capacity"]["unlocked_tiles"]),
        "empty_unlocked_tiles":int(d["uncommitted_capacity"]["empty_unlocked_tiles"]),
        "hands":len(farm.get("hands",[]) or []),
    }


def play(module):
    configure();module.reset_telemetry()
    views={}
    def observed(obs):
        k=(int(obs.get("day",0) or 0),int(obs.get("hour",0) or 0))
        if k in CHECK and f"d{k[0]}h{k[1]}" not in views:
            views[f"d{k[0]}h{k[1]}"]=view(obs)
        return module.agent(obs)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT];players[SEAT]=observed
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    return {
        "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
        "views":views,
        "telemetry":module.get_telemetry(),
    }


def main():
    b=play(baseline);c=play(wr01)
    payload={
        "schema":"kaggriculture.strong-origin-v2.wr01-world-transformation-audit.v0",
        "seed":SEED,"seat":SEAT,
        "baseline":b,"wr01":c,
        "delta_terminal_self":c["terminal"]["self"]-b["terminal"]["self"],
        "wr01_reopened_orders":c["telemetry"].get("reopened_orders",0),
        "wr01_reopened_by_key":c["telemetry"].get("reopened_by_key",{}),
        "boundary":[
            "This audit compares public/self-accessible World State after the unchanged WR-01 intervention.",
            "Checkpoint differences are downstream transformations, not causal attribution to any individual reopened order.",
            "Seed inventory and productive asset/mark remain separate surfaces.",
            "No new Candidate is introduced."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
    print("WR01_WORLD_TRANSFORMATION_AUDIT "+json.dumps({
        "seed":SEED,"seat":SEAT,
        "terminal_delta":payload["delta_terminal_self"],
        "reopened":payload["wr01_reopened_orders"],
        "baseline_views":b["views"],"wr01_views":c["views"]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
