# Clearance

**Plain language in, typed and checked actions out. A contract publishes what it
will ever do; the model may only propose, never widen.**

Live on Testnet Bradbury at
[`0xFB8d9BD944E5ac063880b7D2B5D4c9395Ef6B5c8`](https://explorer-bradbury.genlayer.com/address/0xFB8d9BD944E5ac063880b7D2B5D4c9395Ef6B5c8).
Two unrelated consumer contracts execute cleared actions on chain; see
[Exercised on chain](#exercised-on-chain).

Call it without a local setup: [open it in GenLayer Studio](https://studio.genlayer.com/?import-contract=0xFB8d9BD944E5ac063880b7D2B5D4c9395Ef6B5c8)

## The problem

Letting people speak to a contract in their own words means letting a model
decide what happens. The usual shape is: prompt, parse the reply, execute it.
That makes the model the authority, and every prompt injection, hallucinated
parameter or hallucinated method becomes a state change.

Clearance inverts it. A contract publishes a closed set of actions with the
exact values each parameter accepts, **before** any request exists. The model
gets one job: propose one of those actions. A deterministic check then measures
the proposal against the published rules and refuses anything outside them with
a named reason. The space of possible outcomes is fixed by the schema, not by
what someone writes.

## A published schema

```json
{
  "name": "treasury",
  "actions": [
    {"name": "withdraw", "params": [
      {"name": "to", "type": "address", "allow": ["0x6ab9...d72c", "0xfb33...a67d"]},
      {"name": "amount", "type": "int", "min": 1, "max": 500}
    ]},
    {"name": "pause", "params": []}
  ]
}
```

The schema id is `s` plus the first 32 hex characters of the sha256 of its
canonical form, so widening a limit or adding an address makes a different id
and a consumer bound to the old id keeps its old rules. Unknown keys are
refused, so a typo cannot quietly change what is allowed.

| Parameter type | Accepts |
| --- | --- |
| `int` | whole numbers from `min` to `max`, both inclusive. Never a bool, never a float, never a numeric string |
| `enum` | exactly one of 1 to 8 declared choices |
| `address` | exactly one of 1 to 8 declared addresses, compared lowercase |

There is deliberately no free text parameter: a value no rule can check is a way
back to trusting the model.

## What the model can and cannot do

| | |
| --- | --- |
| The model **can** | propose one action name and a parameter object, or answer `REFUSE` |
| The model **cannot** | invent an action, add or drop a parameter, widen a range, pick an address outside the allowlist, or return free text that anything acts on |

Every refusal carries the rule that stopped it: `UNKNOWN_ACTION`,
`PARAM_MISSING`, `PARAM_UNKNOWN`, `PARAM_TYPE`, `PARAM_RANGE`, `PARAM_CHOICE`,
`PARAM_ALLOW`, or `MODEL_REFUSED`. Out of range values are refused, never
clamped: silently turning 100,000 into 500 would be a payment nobody
authorised.

## How consensus is used

Validators rerun the model call and the checks, then compare
`{"status", "action", "params", "reason"}` by exact equality, with `params` as
canonical JSON with sorted keys. There is no tolerance, because every field is
either a name from a closed set or a canonical rendering of values that already
passed the checks. A reply that is not one action and one parameter object is a
model error, which validators never agree on, so the leader rotates instead of
a guess being stored.

The request text is fenced with a tag derived from the sha256 of the text and
the canonical schema, so it cannot contain its own fence, and a collision is
refused. The structural defence matters more than the fence: a successful
injection can only move the model to a different action or parameters, and both
are then measured against the published rules.

The full argument, failure classes and rejected alternatives are in
[docs/DESIGN.md](docs/DESIGN.md); the interface is in
[docs/INTEGRATING.md](docs/INTEGRATING.md).

## Quick start for a consuming contract

```python
cleared = json.loads(gl.get_contract_at(CLEARANCE).view().get_request(request_id))

if cleared["schema_id"] != MY_SCHEMA_ID:
    raise gl.vm.UserError("[EXPECTED] OTHER_SCHEMA")
if cleared["status"] != "VALID":
    raise gl.vm.UserError("[EXPECTED] NOT_CLEARED")

params = json.loads(cleared["params"])   # already inside your published limits
```

## Honest limitations

1. A cleared action is still the model's reading of a request. The rules bound
   the damage; they do not prove the request meant it. Publish narrow limits.
2. No free text parameters, on purpose. Some requests cannot be expressed.
3. One request, one decision. There is no appeal inside the contract; a refused
   request is re-asked as a new one.
4. Replay protection belongs to the consumer. Both examples keep their own
   executed set.
5. Requests and decisions are public, so the text should not carry secrets.

## Tests

```bash
python -m unittest discover -s tests     # 31 tests, offline, no model
genvm-lint check contracts/clearance.py
```

The suite covers schema canonicalisation and every rejection code, the
parameter truth table (inclusive bounds, bools and numeric strings refused,
addresses on and off the allowlist, missing, extra and renamed parameters),
the decision table from proposal to cleared action or named refusal, the prompt
discipline, exact agreement fixing what a consumer may execute, and both
consumers' plans. Two deliberate mutations, dropping the allowlist check and
coercing a numeric string, both fail it.

## Layout

```
contracts/clearance.py      the primitive, and every rule that votes
contracts/treasury_desk.py  consumer: withdraw within limits, pause
contracts/bot_ops.py        consumer: restart a service, scale replicas
tests/test_clearance.py     the suite
docs/INTEGRATING.md         publish, request, execute
docs/DESIGN.md              claim, agreement, failure classes, limits
```

## Licence

MIT, see [LICENSE](LICENSE).
