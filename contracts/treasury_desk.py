# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""TreasuryDesk: a consumer that executes only cleared actions.

It holds no model and no web access. It reads one cleared request from
Clearance, checks that the request was cleared for this contract's own rules
and raised by the caller, then executes the action it declared.
"""

import json
import typing
from genlayer import *

ACTIONS = ("withdraw", "pause")
ERROR_EXPECTED = "[EXPECTED]"


def plan(cleared: dict) -> tuple:
    """Read a cleared record into exactly what this contract will do."""
    if cleared.get("status") != "VALID":
        raise ValueError("NOT_CLEARED")
    action = cleared.get("action")
    if action not in ACTIONS:
        raise ValueError("NOT_MY_ACTION")
    params = json.loads(cleared.get("params") or "{}")
    if action == "withdraw":
        return "withdraw", str(params["to"]), int(params["amount"])
    return "pause", "", 0


def same_subject(cleared: dict, sender: str) -> bool:
    return str(cleared.get("subject", "")).lower() == str(sender).lower()


def _fail(code: str) -> typing.NoReturn:
    raise gl.vm.UserError(ERROR_EXPECTED + " " + code)


class TreasuryDesk(gl.Contract):
    clearance: Address
    schema_id: str
    paused: bool
    paid_out: u256
    payments: DynArray[str]
    executed: TreeMap[str, str]

    def __init__(self, clearance: typing.Any, schema_id: str) -> None:
        self.clearance = clearance if isinstance(clearance, Address) else Address(str(clearance))
        self.schema_id = str(schema_id)
        published = json.loads(gl.get_contract_at(self.clearance).view().get_schema(self.schema_id))
        declared = [action["name"] for action in published["actions"]]
        for name in ACTIONS:
            if name not in declared:
                _fail("SCHEMA_MISSING_ACTION")
        self.paused = False
        self.paid_out = u256(0)

    @gl.public.write
    def execute(self, request_id: str) -> None:
        rid = str(request_id)
        if rid in self.executed:
            _fail("ALREADY_EXECUTED")
        cleared = json.loads(gl.get_contract_at(self.clearance).view().get_request(rid))
        if str(cleared["schema_id"]) != str(self.schema_id):
            _fail("OTHER_SCHEMA")
        if not same_subject(cleared, str(gl.message.sender_address)):
            _fail("NOT_THE_SUBJECT")
        try:
            action, to, amount = plan(cleared)
        except ValueError as err:
            _fail(str(err))
        except Exception:
            _fail("CLEARED_RECORD_UNREADABLE")
        if action == "pause":
            self.paused = True
        else:
            if self.paused:
                _fail("PAUSED")
            self.paid_out = u256(int(self.paid_out) + amount)
            self.payments.append(json.dumps({"to": to, "amount": amount}, sort_keys=True))
        self.executed[rid] = action

    @gl.public.view
    def status(self) -> str:
        return json.dumps({"paused": bool(self.paused), "paid_out": int(self.paid_out),
                           "payments": [str(p) for p in self.payments],
                           "schema_id": str(self.schema_id),
                           "executed": len(self.payments) + (1 if self.paused else 0)},
                          sort_keys=True)
