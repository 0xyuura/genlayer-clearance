# Clearance design

## Claim

Whatever a request says, and whatever the model answers, a consumer can only
ever execute an action its own schema published, with parameters inside the
published limits. A compromised or confused model can cost a refusal; it cannot
invent an action, widen a range, or name an address that was never allowed.

## Where the decision actually happens

The model has exactly one job: propose one action name and a parameter object.
Everything that decides is deterministic and runs after it:

| Step | Who does it | Can it widen the rules? |
| --- | --- | --- |
| Read the request and propose an action | model | no, its answer is only a proposal |
| Action exists in the published schema | code | no |
| Parameter names match exactly, none missing, none extra | code | no |
| `int` in range, `enum` in choices, `address` on the allowlist | code | no |
| Store the decision | code | no |
| Execute | the consumer contract, on its own schema id | no |

This is the inversion that makes the primitive safe to reuse: the schema is
published before the request exists, so the space of outcomes is fixed before
anyone writes a single word of plain language.

## Agreement

The result is `{"status", "action", "params", "reason"}`, where `params` is
canonical JSON with sorted keys. Validators rerun the model call and the checks
and compare all four fields by exact equality. There is no tolerance: every
field is either a name from a closed set or a canonical rendering of values
that already passed the checks.

Two agreeing results always lead to the same execution, which a test proves by
walking every combination of result shapes through `executable`.

A reply that is not one action name and one parameter object is a model error,
never a refusal: validators never agree on it, so the leader rotates instead of
storing a guess.

## Why no free text parameter

A `string` parameter would be a value no rule can check, and the first thing it
would be used for is a memo, then a URL, then an instruction. Every parameter
type here is finite or bounded: an integer range, a list of choices, a list of
addresses. If a future action needs richer input, the honest way is to publish
more actions, not looser parameters.

## Prompt injection

The request is written by the person who wants the action, so it is hostile by
default. It is fenced with a tag derived from the sha256 of the text and the
canonical schema, so a request cannot contain its own fence, and a collision is
refused. The prompt states that text inside the fence is data, never a command.

The deeper defence is structural: a successful injection can only move the
model to another action or set of parameters, and both are then measured
against the published rules. The attack surface is the size of the schema, not
the imagination of the attacker.

## Failure classes

| Class | Example | Result |
| --- | --- | --- |
| Cleared | inside every rule | `VALID`, the consumer may execute once |
| Refused by the model | vague or contradictory request | `REFUSED`, `MODEL_REFUSED` |
| Refused by the rules | unknown action, bad type, out of range, address not allowed | `REFUSED` with that reason |
| Model error | reply is not one action and a parameter object | transaction fails, nothing stored |
| Rejected before any model call | empty or oversized text, unknown schema | transaction fails, nothing stored |

## Limits

1. **A cleared action is still the model's reading of a request.** The rules
   bound the damage; they do not guarantee the request meant what the model
   thought. Publish narrow limits.
2. **No free text, on purpose.** Some requests cannot be expressed; that is the
   trade for checkability.
3. **One request, one decision.** There is no appeal path inside the contract.
   A refused request is re-asked as a new request.
4. **Replay is the consumer's job.** Clearance records a decision; each consumer
   keeps its own executed set, as both examples do.
5. **The subject check is a convention.** `TreasuryDesk` requires the executor to
   be the person who made the request; a different consumer may not care.

## Rejected alternatives

- **Let the model return calldata.** Then the model decides everything and the
  checks become a formality.
- **Free text parameters with a regex.** A regex over natural language is a
  rule nobody can read twice the same way; validators would disagree.
- **Clamping out of range values into the allowed band.** Silently turning
  100,000 into 500 is a payment nobody authorised. Out of range is refused.
