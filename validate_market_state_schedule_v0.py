#!/usr/bin/env python3
import json
from pathlib import Path
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

d=json.loads(Path("market_state_schedule_v0.json").read_text(encoding="utf-8"))
assert d["world"]["public_rule_commit"]=="b2405492c8403f6649f9317290f215e0290a2425"
assert d["market_initial_state"]["inventory_per_product"]==kg.MARKET_I0==10000
assert d["market_initial_state"]["price_floor"]==kg.PRICE_FLOOR==1
for item,p in d["products"].items():
    assert kg.MARKET_PARAMS[item]==p,(item,kg.MARKET_PARAMS[item],p)

assert d["order_surface"]["max_market_orders_per_turn_default"]==10
assert d["order_surface"]["buy_product_shed_capacity_default"]==100
assert d["exogenous_market_demand"]["town_shop_sell_interval_default_turns"]==4
assert d["exogenous_market_demand"]["town_center_sell_interval_default_turns"]==24
assert d["exogenous_market_demand"]["shop_unlock_interval_days_default"]==3
assert d["exogenous_market_demand"]["max_shop_instances"]==kg.MAX_SHOP_INSTANCES==8

anchors={}
for item,p in kg.MARKET_PARAMS.items():
    inv0=p["I0"];T=p["T"]
    anchors[item]={
      "I0_minus_T":kg.market_price(item,inv0-T),
      "I0":kg.market_price(item,inv0),
      "I0_plus_T":kg.market_price(item,inv0+T)
    }

print(json.dumps({
  "schema":d["schema"],"schedule_id":d["schedule_id"],
  "status":"PASS","price_anchors":anchors
},separators=(",",":")))
