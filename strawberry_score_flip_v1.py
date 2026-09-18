"""Minimal STRAWBERRY score flip near the observed Turn108 boundary.

Only while call/turn is 98..108, if WHEAT narrowly leads STRAWBERRY by <= 0.04,
raise only STRAWBERRY score by +0.04. Everything else is delegated unchanged.
"""
import strong_origin
import whole_flow_control_agent as v6

DELTA=0.04
START=98
END=108
_turn=-1
_activations=[]

def reset_experiment():
    global _turn,_activations
    _turn=-1
    _activations=[]

def get_activations():
    return list(_activations)

def agent(obs):
    global _turn
    _turn += 1
    original=strong_origin.counter_crop_weights

    def patched(field, base_price, town_demand):
        scores=dict(original(field,base_price,town_demand))
        s=float(scores.get("STRAWBERRY",0.0) or 0.0)
        w=float(scores.get("WHEAT",0.0) or 0.0)
        gap=w-s
        if START <= _turn <= END and 0.0 < gap <= DELTA:
            scores["STRAWBERRY"]=s+DELTA
            _activations.append({"turn":_turn,"before_strawberry":s,"wheat":w,"gap":gap,"after_strawberry":scores["STRAWBERRY"]})
        return scores

    strong_origin.counter_crop_weights=patched
    try:
        return v6.agent(obs)
    finally:
        strong_origin.counter_crop_weights=original
