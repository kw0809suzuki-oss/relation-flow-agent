# COW Purchase Ledger v0

Confirmed source fact:
g8_agent.py defines ANIMAL_COST={"COW":400} and subtracts 400 from its internal available_cash when it appends BUY_ANIMAL COW.
Money Path Ledger priced BUY_ANIMAL via market prices, so COW can be under-accounted if market prices do not carry that cost.

Observer only. Fresh10.
For every turn requesting BUY_ANIMAL COW:
money delta - priced market net excluding COW = residual.
Then test whether residual + 400*COW units collapses toward zero.

Boundary:
This is a ledger-consistency probe. BUY_ANIMAL request is not automatically called a settled purchase.
