#!/usr/bin/env python3
"""Observation-only replay action audit around SB-01 Day 7 expansion.

Runs the exact fixed SB-01 matchup. After completion, reads Kaggle replay
state (env.steps) to inspect recorded actions for both players. No action is
modified.
"""
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"sb01_replay_action_audit_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def slim_obs(obs):
    if not isinstance(obs, dict): return {}
    farms=obs.get("farms") or []
    return {
        "day":obs.get("day"),
        "turn":obs.get("turn"),
        "step":obs.get("step"),
        "farm_public":[{
            "money":f.get("money"),
            "hands":len(f.get("hands",[]) or []),
            "hires_today":f.get("hires_today"),
            "unlocked_quadrants":list(f.get("unlocked_quadrants",[]) or []),
        } for f in farms]
    }

def main():
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]
    players[SEAT]=combat.agent
    env.run(players)

    rows=[]
    for step_idx, states in enumerate(env.steps):
        if not isinstance(states, list) or len(states)<2: continue
        # each state carries that player's own observation/action
        st_self=states[SEAT]
        obs=getattr(st_self,"observation",None)
        if obs is None and isinstance(st_self,dict): obs=st_self.get("observation")
        obs=dict(obs) if obs is not None else {}
        day=obs.get("day")
        if day!=7: continue
        actions=[]
        for pid,st in enumerate(states):
            a=getattr(st,"action",None)
            if a is None and isinstance(st,dict): a=st.get("action")
            actions.append(a)
        rows.append({
            "step_index":step_idx,
            "self_observation":slim_obs(obs),
            "actions_by_player":actions,
        })

    payload={
      "schema":"kaggriculture.sb01.replay-action-audit.v0",
      "probe":"Remaining Strength Gap Replay Action Audit",
      "mode":"observation_only_replay",
      "seed":SEED,"seat":SEAT,"snapshot":"SB-01",
      "day7_rows":rows,
      "boundary":[
        "No strategy, rule, threshold, or candidate is changed.",
        "Recorded actions are read only after env.run from replay state.",
        "This probe verifies whether opponent actions are directly recoverable; it does not infer missing actions."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SB01_REPLAY_ACTION_AUDIT_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
