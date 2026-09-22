#!/usr/bin/env python3
"""Option Preservation Abstraction Probe v0.

Pure A/B abstraction probe.
- Baseline: no outer abstraction.
- Probe: D14+ OPTION_PRESERVATION semantic context only.
No action instruction, strategy instruction, numeric rule, commitment scaling,
or direct action rewrite.
"""

import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"option_preservation_abstraction_probe_v0_{SEED}.json")

def configure(option=False):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    os.environ.pop("OUTER_MEANING_CLOSURE_DAY",None)
    if option:
        os.environ["OUTER_MEANING_OPTION_PRESERVATION_DAY"]="14"
    else:
        os.environ.pop("OUTER_MEANING_OPTION_PRESERVATION_DAY",None)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(option=False):
    configure(option)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]
    players[SEAT]=combat.agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    snaps=snapshots(combat.get_trace())
    compact=[]
    for s in snaps:
        if int(s.get("day",0) or 0)<14:
            continue
        internal=dict(s.get("origin_internal",{}) or {})
        reading=dict(s.get("origin_reading_current",{}) or {})
        integ=dict(s.get("origin_integration_current",{}) or {})
        compact.append({
            "turn":s.get("turn"),"day":s.get("day"),
            "strategy":internal.get("strategy_name"),
            "targets":internal.get("targets"),
            "best_crop":internal.get("best_crop"),
            "scores":internal.get("scores"),
            "market":internal.get("market"),
            "farmer_action":internal.get("farmer_action"),
            "hand_actions":internal.get("hand_actions"),
            "final_action":s.get("action"),
            "outer_meaning_present":integ.get("outer_meaning_present"),
            "outer_phase":integ.get("outer_phase"),
            "meaning_commitment_scale":integ.get("meaning_commitment_scale"),
            "action_instruction":integ.get("action_instruction"),
            "strategy_instruction":integ.get("strategy_instruction"),
            "reading_field_context_present":reading.get("field_context_present"),
        })
    return {"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],"snapshots":compact}

def diff_rows(a,b):
    by_turn={x["turn"]:x for x in a}
    out=[]
    keys=("strategy","targets","best_crop","scores","market","farmer_action","hand_actions","final_action")
    for y in b:
        x=by_turn.get(y["turn"])
        if x is None: continue
        changed=[k for k in keys if x.get(k)!=y.get(k)]
        if changed:
            out.append({"turn":y["turn"],"day":y["day"],"changed":changed})
    return out

def main():
    baseline=play(False)
    probe=play(True)
    diffs=diff_rows(baseline["snapshots"],probe["snapshots"])
    meaning_rows=[x for x in probe["snapshots"] if x.get("outer_meaning_present")]
    payload={
        "schema":"kaggriculture.option-preservation-abstraction-probe.v0",
        "seed":SEED,"seat":SEAT,
        "baseline_terminal":{"self":baseline["self"],"opponent":baseline["opponent"],"margin":baseline["margin"]},
        "probe_terminal":{"self":probe["self"],"opponent":probe["opponent"],"margin":probe["margin"]},
        "meaning_received_turns":len(meaning_rows),
        "meaning_phases":sorted({str(x.get("outer_phase")) for x in meaning_rows}),
        "meaning_scales":sorted({x.get("meaning_commitment_scale") for x in meaning_rows}),
        "model_response_changed_turns":len(diffs),
        "model_response_diffs":diffs[:50],
        "terminal_self_diff":probe["self"]-baseline["self"],
        "terminal_margin_diff":probe["margin"]-baseline["margin"],
        "boundary":[
            "Pure semantic-context probe only.",
            "No direct action or strategy instruction.",
            "No numeric rule, threshold, cap, suppression, or forced action.",
            "ORIGIN_CROP_COMMITMENT is explicitly disabled.",
            "OPTION_PRESERVATION is not mapped to a special commitment scale.",
            "A zero response is valid evidence that context arrived but was not operationally interpreted."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("OPTION_PRESERVATION_ABSTRACTION_PROBE_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
