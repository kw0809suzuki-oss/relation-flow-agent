#!/usr/bin/env python3
"""Validate Asset State Schedule v0 against installed Kaggriculture public constants.

This is a provenance/consistency check, not a Battle analysis.
"""
import json
from pathlib import Path
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

PATH=Path("asset_state_schedule_v0.json")
d=json.loads(PATH.read_text(encoding="utf-8"))

assert d["world"]["public_rule_commit"]=="b2405492c8403f6649f9317290f215e0290a2425"
assert d["world"]["default_turns_per_day"]==24
assert d["world"]["default_episode_steps"]==720

expected_crops={
 "WHEAT":{"seed":10,"first_yield_day":2,"max_yield_day":4,"interval":0,"max_yield":6,"ongoing":False},
 "MELON":{"seed":80,"first_yield_day":10,"max_yield_day":12,"interval":0,"max_yield":6,"ongoing":False},
 "STRAWBERRY":{"seed":100,"first_yield_day":10,"max_yield_day":10,"interval":2,"max_yield":4,"ongoing":True},
}
expected_animals={
 "COW":{"cost":400,"structure":"PASTURE","first_yield_day":8,"interval":2,"max_held":6,"product":"MILK"},
 "SHEEP":{"cost":500,"structure":"PASTURE","first_yield_day":6,"interval":3,"max_held":6,"product":"WOOL"},
}
for k,v in expected_crops.items():
    assert kg.CROPS[k]==v,(k,kg.CROPS[k],v)
for k,v in expected_animals.items():
    assert kg.ANIMALS[k]==v,(k,kg.ANIMALS[k],v)

a=d["assets"]
assert a["WHEAT"]["production"]["water_yield_window_day_offsets"]==[2,3,4]
assert a["WHEAT"]["production"]["no_fertilizer_max_held_if_all_window_waters"]==4
assert a["MELON"]["production"]["water_yield_window_day_offsets"]==[6,7,8,9,10,11,12]
assert a["MELON"]["production"]["no_fertilizer_max_held_if_all_window_waters"]==6
assert a["STRAWBERRY"]["production"]["base_output_event_day_offsets"]==[10,12,14,16]
assert a["COW"]["production"]["first_output_day_offset"]==8
assert a["COW"]["production"]["repeat_interval_days"]==2
assert a["SHEEP"]["production"]["first_output_day_offset"]==6
assert a["SHEEP"]["production"]["repeat_interval_days"]==3

for name in ("WHEAT","MELON","STRAWBERRY","COW","SHEEP"):
    assert a[name]["productive_entry"]["tile_occupancy"]==1

print(json.dumps({
 "schema":d["schema"],
 "schedule_id":d["schedule_id"],
 "validated_assets":["WHEAT","MELON","STRAWBERRY","COW","SHEEP"],
 "public_rule_commit":d["world"]["public_rule_commit"],
 "status":"PASS"
},separators=(",",":")))
