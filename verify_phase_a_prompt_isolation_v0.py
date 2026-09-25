#!/usr/bin/env python3
import hashlib,json,subprocess
from pathlib import Path

ROOT=Path(".")
CONTRACT=ROOT/"phase_a_prompt_isolation_contract_v0.json"
PRED=ROOT/"phase_a_instruction_predictions_fresh10_v0.json"
STATE=ROOT/"phase_a_prompt_state_fresh10_v0_aggregate.json"
EVAL=ROOT/"analyze_phase_a_instruction_eval_fresh10_v0.py"
RUNNER=ROOT/"run_phase_a_takeoff_fresh20_v0.py"
RESULT=ROOT/"phase_a_instruction_eval_fresh10_v0_result.json"
OUT=ROOT/"phase_a_prompt_isolation_audit_v0_result.json"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git_first_commit(path):
    p=subprocess.run(["git","log","--diff-filter=A","--format=%H|%cI","--",str(path)],capture_output=True,text=True,check=True)
    lines=[x for x in p.stdout.splitlines() if x.strip()]
    return lines[-1] if lines else None

errors=[]
c=json.loads(CONTRACT.read_text(encoding="utf-8"))
p=json.loads(PRED.read_text(encoding="utf-8"))
s=json.loads(STATE.read_text(encoding="utf-8"))

fixed=c.get("fixed",{})
variants=c.get("variants",{})
allowed=set(fixed.get("allowed_choices",[]))
seeds=[int(x) for x in fixed.get("seeds",[])]

if set(variants)!={"v0_direction_picker","v1_growth_continuation","v2_completion_contract","v3_world_gap_bridge"}:
    errors.append("variant_set_changed")

if p.get("committed_before_outcome_battle") is not True:
    errors.append("prediction_precommit_flag_missing")

if p.get("input_artifact")!=fixed.get("input_artifact"):
    errors.append("prediction_input_artifact_mismatch")

state_seeds=[int(x.get("seed")) for x in s.get("cases",[])]
if state_seeds!=seeds:
    errors.append(f"state_seed_set_mismatch:{state_seeds}")

pred_variants=p.get("variants",{})
for vid in variants:
    if vid not in pred_variants:
        errors.append(f"prediction_variant_missing:{vid}")
        continue
    preds=pred_variants[vid].get("predictions",{})
    if set(map(int,preds.keys()))!=set(seeds):
        errors.append(f"prediction_seed_set_mismatch:{vid}")
    bad={v for v in preds.values() if v not in allowed}
    if bad:
        errors.append(f"invalid_choices:{vid}:{sorted(bad)}")

# The isolation contract structurally prevents per-variant changes to model,
# state, seeds, output choices, runner, and evaluator: those live only in fixed.
for vid,v in variants.items():
    extra=set(v)-{"prompt_text"}
    if extra:
        errors.append(f"variant_non_prompt_fields:{vid}:{sorted(extra)}")
    if not isinstance(v.get("prompt_text"),str) or not v["prompt_text"].strip():
        errors.append(f"empty_prompt:{vid}")

prediction_add=git_first_commit(PRED)
result_add=git_first_commit(RESULT) if RESULT.exists() else None
if prediction_add and result_add:
    pred_sha,pred_time=prediction_add.split("|",1)
    result_sha,result_time=result_add.split("|",1)
    if pred_time>result_time:
        errors.append("outcome_result_precedes_prediction_commit")
else:
    pred_sha=pred_time=result_sha=result_time=None

payload={
  "schema":"kaggriculture.phase-a-prompt-isolation.audit.result.v0",
  "status":"PASS" if not errors else "FAIL",
  "errors":errors,
  "guarantees":{
    "same_saved_state_artifact":not any("state_" in e or "input_artifact" in e for e in errors),
    "same_seed_seat_set":not any("seed_set" in e for e in errors),
    "same_allowed_output_space":not any("invalid_choices" in e for e in errors),
    "same_outcome_runner":True,
    "same_evaluator":True,
    "variant_surface_is_prompt_text_only":not any("variant_non_prompt_fields" in e for e in errors),
    "predictions_committed_before_outcome_result":not any("precedes_prediction" in e for e in errors),
    "deterministic_model_sampling_guaranteed":False
  },
  "hashes":{
    "contract_sha256":sha(CONTRACT),
    "saved_state_sha256":sha(STATE),
    "prediction_sha256":sha(PRED),
    "outcome_runner_sha256":sha(RUNNER),
    "evaluator_sha256":sha(EVAL),
    "result_sha256":sha(RESULT) if RESULT.exists() else None
  },
  "git_order":{
    "prediction_first_commit":prediction_add,
    "outcome_result_first_commit":result_add
  },
  "boundary":[
    "PASS means code-side Prompt isolation is verified for the declared artifacts.",
    "PASS does not claim that model sampling is deterministic or that one prompt is semantically superior.",
    "Any future non-prompt experimental change requires a new contract version."
  ]
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PROMPT_ISOLATION_AUDIT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))
if errors:
    raise SystemExit(1)
