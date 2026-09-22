# Flow-chan Guidance Autonomy v0

Core idea:

> Flow-chan: "今の私の考え方はこう。でもStateを見て自分で考えてね。"

Flow-chan supplies:
- a current perspective
- an explicit autonomy clause
- a search task
- no mandatory domain, threshold, action, or winner

Model-side proxy may:
- use throughput_match
- use throughput_with_slack
- keep native behavior
depending on the current State.

Boundary:
This run uses a scripted proxy for model self-direction. It tests the interface
shape "guidance, not command"; it does not prove free-form model autonomy.

Battle compares:
- control
- fixed throughput_match reference
- guided_autonomy

No automatic adoption. All abstractions and model choices remain hypotheses.
