#!/usr/bin/env python3
"""Observe late WHEAT divergence window on fresh seeds without terminal/margin labels."""
import importlib.util, json
from pathlib import Path
from kaggle_environments import make
import strong_origin_g5_roi as baseline_agent
import full_strong_origin_v1 as candidate_agent

OPPONENT_PATH='opponents/seyamalam_v21.py'
CASES=((3564,0),(3565,1),(3566,0),(3567,1),(3568,0))
START=110
END=120

def load_opp(tag):
    spec=importlib.util.spec_from_file_location(f'opp_{tag}',OPPONENT_PATH)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod.agent

def play(seed,seat,self_module,tag):
    self_module.reset_telemetry(); self_trace=[]; opp_trace=[]; opp=load_opp(tag)
    env=make('kaggriculture',configuration={'seed':seed},debug=False)
    def sw(obs):
        t=len(self_trace); a=self_module.agent(obs); m=obs.get('market',{})
        self_trace.append({'turn':t,'wheat_inventory':m.get('inventory',{}).get('WHEAT'),'wheat_price':m.get('prices',{}).get('WHEAT'),'action':a}); return a
    def ow(obs):
        t=len(opp_trace); a=opp(obs); opp_trace.append({'turn':t,'action':a}); return a
    players=[ow,ow]; players[seat]=sw; players[1-seat]=ow; env.run(players)
    return self_trace,opp_trace

def wheat_market(action):
    if not isinstance(action,dict): return []
    out=[]
    for x in action.get('market',[]) or []:
        if isinstance(x,(list,tuple)) and len(x)>=2 and x[1]=='WHEAT': out.append(list(x))
    return out

def main():
    cases=[]
    for seed,seat in CASES:
        bs,bo=play(seed,seat,baseline_agent,f'b{seed}'); cs,co=play(seed,seat,candidate_agent,f'c{seed}')
        rows=[]
        for t in range(START,END+1):
            bi=bs[t]['wheat_inventory']; ci=cs[t]['wheat_inventory']; d=ci-bi
            prev=None if t==0 else cs[t-1]['wheat_inventory']-bs[t-1]['wheat_inventory']
            rows.append({
                'turn':t,'delta':d,'delta_step':None if prev is None else d-prev,
                'baseline_wheat_inventory':bi,'candidate_wheat_inventory':ci,
                'baseline_wheat_price':bs[t]['wheat_price'],'candidate_wheat_price':cs[t]['wheat_price'],
                'self_action_equal':bs[t]['action']==cs[t]['action'],
                'opp_action_equal':bo[t]['action']==co[t]['action'],
                'baseline_self_wheat_market':wheat_market(bs[t]['action']),
                'candidate_self_wheat_market':wheat_market(cs[t]['action'])
            })
        cases.append({'seed':seed,'seat':seat,'rows':rows})
    result={'schema':'kaggriculture.full-v1-wheat-late-window.v1','observer_only':True,'agent_mutated':False,'terminal_read':False,'margin_read':False,'window':[START,END],'cases':cases}
    Path('full_v1_wheat_late_window.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('WHEAT_LATE_WINDOW '+json.dumps(cases,separators=(',',':')))
if __name__=='__main__': main()
