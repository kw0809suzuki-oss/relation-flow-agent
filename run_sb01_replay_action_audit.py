#!/usr/bin/env python3
"""Observation-only replay action audit around SB-01 expansion.

Runs the exact fixed SB-01 matchup. After completion, reads Kaggle replay
state (env.steps) to inspect recorded actions for both players. No action is
modified. This version also preserves the raw public farm observations for
the narrow Day 7 expansion window so spatial placement can be verified.
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

def state_obs(states):
    if not isinstance(states, list) or len(states)<2:
        return {}
    st_self=states[SEAT]
    obs=getattr(st_self,"observation",None)
    if obs is None and isinstance(st_self,dict):
        obs=st_self.get("observation")
    return dict(obs) if obs is not None else {}

def state_actions(states):
    if not isinstance(states, list) or len(states)<2:
        return []
    actions=[]
    for st in states:
        a=getattr(st,"action",None)
        if a is None and isinstance(st,dict):
            a=st.get("action")
        actions.append(a)
    return actions

def jsonable(value):
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except Exception:
        return str(value)

def main():
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]
    players[SEAT]=combat.agent
    env.run(players)

    day7_rows=[]
    expansion_window_raw=[]
    snapshots=[]
    for step_idx, states in enumerate(env.steps):
        obs=state_obs(states)
        if not obs:
            continue
        actions=state_actions(states)
        snap={
            "step_index":step_idx,
            "observation":slim_obs(obs),
            "actions_by_player":actions,
        }
        snapshots.append(snap)
        if obs.get("day")==7:
            day7_rows.append({
                "step_index":step_idx,
                "self_observation":slim_obs(obs),
                "actions_by_player":actions,
            })
        if 169 <= step_idx <= 176:
            expansion_window_raw.append({
                "step_index":step_idx,
                "day":obs.get("day"),
                "farms":jsonable(obs.get("farms") or []),
                "actions_by_player":jsonable(actions),
            })

    quadrant_transitions=[]
    for prev,cur in zip(snapshots,snapshots[1:]):
        pf=prev["observation"].get("farm_public") or []
        cf=cur["observation"].get("farm_public") or []
        for pid in range(min(len(pf),len(cf))):
            pqs=pf[pid].get("unlocked_quadrants") or []
            cqs=cf[pid].get("unlocked_quadrants") or []
            if len(cqs)!=len(pqs):
                quadrant_transitions.append({
                    "player_id":pid,
                    "role":"self" if pid==SEAT else "opponent",
                    "from_step_index":prev["step_index"],
                    "to_step_index":cur["step_index"],
                    "from_observation":prev["observation"],
                    "to_observation":cur["observation"],
                    "actions_at_from_step":prev["actions_by_player"],
                    "actions_at_to_step":cur["actions_by_player"],
                })

    buy_land_occurrences=[]
    for snap in snapshots:
        for pid,action in enumerate(snap["actions_by_player"]):
            market=(action or {}).get("market",[]) if isinstance(action,dict) else []
            if any(isinstance(x,(list,tuple)) and x and x[0]=="BUY_LAND" for x in market):
                buy_land_occurrences.append({
                    "player_id":pid,
                    "role":"self" if pid==SEAT else "opponent",
                    "step_index":snap["step_index"],
                    "observation":snap["observation"],
                    "action":action,
                })

    payload={
      "schema":"kaggriculture.sb01.replay-action-audit.v3",
      "probe":"Remaining Strength Gap Replay Action Audit",
      "mode":"observation_only_replay",
      "seed":SEED,"seat":SEAT,"snapshot":"SB-01",
      "day7_rows":day7_rows,
      "expansion_window_raw":expansion_window_raw,
      "quadrant_transitions":quadrant_transitions,
      "buy_land_occurrences":buy_land_occurrences,
      "tracked_ne_melon":{
        "coordinate":[1,5],
        "rows":[
          {
            "step_index":step_idx,
            "day":obs.get("day"),
            "money":[f.get("money") for f in (obs.get("farms") or [])],
            "tile_row1_col5":[
              jsonable((f.get("tiles") or [])[1][5])
              if len(f.get("tiles") or []) > 1 and len((f.get("tiles") or [])[1]) > 5
              else None
              for f in (obs.get("farms") or [])
            ],
            "actions_by_player":jsonable(state_actions(states)),
          }
          for step_idx, states in enumerate(env.steps)
          for obs in [state_obs(states)]
          if obs and 176 <= step_idx <= 320
        ],
      },
      "boundary":[
        "No strategy, rule, threshold, or candidate is changed.",
        "Recorded replay actions are agent-submitted actions; successful environment effect is verified separately by public-state transition.",
        "A quadrant transition is recorded only when unlocked_quadrants changes in consecutive replay observations.",
        "Raw farm observations are preserved only for step 169 through 176 to verify spatial placement without broadening the observer.",
        "The tracked NE MELON window preserves only coordinate row 1, col 5, player money, and actions from step 176 through 320; no causal attribution is added.",
        "No missing action or causal relation is inferred."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SB01_REPLAY_ACTION_AUDIT_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
