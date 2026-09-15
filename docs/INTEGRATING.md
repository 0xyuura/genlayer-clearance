# Integrating Clearance

Clearance turns a plain language request into an action your contract already
declared, or into a refusal. Your contract holds no model and no web access: it
reads a cleared record and executes it.

## 1. Publish what your contract will ever do

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

`publish` accepts this as JSON text or as a calldata object and returns the
schema id, which is `s` plus the first 32 hex characters of the sha256 of the
canonical form. Publishing the same rules twice returns the same id.
`schema_id_for` computes it without storing anything.

| Field | Rules |
| --- | --- |
| `name` | lowercase letters, digits and underscore, at most 32 characters |
| `actions` | 1 to 8, unique names, never `REFUSE` |
| `params` | 0 to 4 per action, unique names |
| `type: int` | `min` and `max` whole numbers, `min <= max`, both inclusive |
| `type: enum` | `choices`, 1 to 8 distinct labels |
| `type: address` | `allow`, 1 to 8 distinct addresses, stored lowercase |

Unknown keys are refused, so a typo can never quietly widen what is allowed.
Widening a limit or adding an address produces a different schema id, so a
consumer bound to the old id keeps its old rules.

## 2. Ask in plain language

`request(schema_id, text)` stores a record and returns its id. The model sees
the request fenced as untrusted data, together with the published actions and
their limits, and must answer with one action and its parameters, or `REFUSE`.

What the deterministic check does with that proposal:

| Outcome | `status` | `reason` |
| --- | --- | --- |
| Action and parameters inside the published rules | `VALID` | empty |
| The model declined | `REFUSED` | `MODEL_REFUSED` |
| An action that is not published | `REFUSED` | `UNKNOWN_ACTION` |
| A parameter that is missing, extra, wrongly typed, out of range, not an allowed choice or not an allowed address | `REFUSED` | `PARAM_MISSING`, `PARAM_UNKNOWN`, `PARAM_TYPE`, `PARAM_RANGE`, `PARAM_CHOICE`, `PARAM_ALLOW` |
| A reply that is not one action and an object of parameters | the transaction fails as a model error, nothing is stored |

Numbers are never coerced: `"200"` and `200.0` are refused, not read as 200.
Booleans are not numbers. Addresses are compared against the allowlist after
lowercasing, and nothing else is accepted.

## 3. Execute in your contract

```python
cleared = json.loads(gl.get_contract_at(CLEARANCE).view().get_request(request_id))

if cleared["schema_id"] != MY_SCHEMA_ID:       # rules you did not publish
    raise gl.vm.UserError("[EXPECTED] OTHER_SCHEMA")
if cleared["subject"].lower() != str(gl.message.sender_address).lower():
    raise gl.vm.UserError("[EXPECTED] NOT_THE_SUBJECT")
if cleared["status"] != "VALID":
    raise gl.vm.UserError("[EXPECTED] NOT_CLEARED")

params = json.loads(cleared["params"])         # already checked against your rules
```

Both example consumers do exactly this, and both refuse a request cleared for a
different schema. `TreasuryDesk` additionally requires the caller to be the
person who made the request, and keeps its own `executed` map so one cleared
record cannot be replayed.

| View | Returns |
| --- | --- |
| `get_request(request_id)` | JSON: `subject`, `schema_id`, `text`, `status`, `action`, `params`, `reason`, `created_at` |
| `get_schema(schema_id)` | the canonical published rules |
| `schema_id_for(schema)` | the id of a schema without storing it |
| `counts()` | how many schemas and requests exist |

## 4. Rules of thumb

- Publish the narrowest limits you can live with. The model cannot widen them,
  but a wide `max` is a wide `max` for everyone.
- Keep parameters typed. There is no free text parameter on purpose: a string
  nobody can check is a way back to trusting the model.
- Bind your consumer to one schema id at construction and verify your actions
  exist there, as both examples do.
- Treat `REFUSED` as information, not an error. The reason names exactly which
  rule stopped it.
