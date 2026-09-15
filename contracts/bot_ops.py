# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""BotOps: a second, unrelated consumer of the same Clearance contract.

Different actions, different parameter types, same guarantee: the model can
only ever hand this contract one of the actions it published, with parameters
inside the published limits.
"""

import json
import typing
from genlayer import *

ACTIONS = ("restart", "scale")
ERROR_EXPECTED = "[EXPECTED]"


def plan(cleared: dict) -> tuple:
    if cleared.get("status") != "VALID":
        raise ValueError("NOT_CLEARED")
    action = cleared.get("action")
    if action not in ACTIONS:
        raise ValueError("NOT_MY_ACTION")
    params = json.loads(cleared.get("params") or "{}")
    if action == "restart":
        return "restart", str(params["service"]), 0
    return "scale", "", int(params["replicas"])


def _fail(code: str) -> typing.NoReturn:
    raise gl.vm.UserError(ERROR_EXPECTED + " " + code)


class BotOps(gl.Contract):
    clearance: Address
    schema_id: str
    replicas: u256
    last_action: str
    last_service: str
    log: DynArray[str]
    executed: TreeMap[str, str]

    def __init__(self, clearance: typing.Any, schema_id: str, replicas: int) -> None:
        self.clearance = clearance if isinstance(clearance, Address) else Address(str(clearance))
        self.schema_id = str(schema_id)
        published = json.loads(gl.get_contract_at(self.clearance).view().get_schema(self.schema_id))
        declared = [action["name"] for action in published["actions"]]
        for name in ACTIONS:
            if name not in declared:
                _fail("SCHEMA_MISSING_ACTION")
        self.replicas = u256(int(replicas))
        self.last_action = ""
        self.last_service = ""

    @gl.public.write
    def execute(self, request_id: str) -> None:
        rid = str(request_id)
        if rid in self.executed:
            _fail("ALREADY_EXECUTED")
        cleared = json.loads(gl.get_contract_at(self.clearance).view().get_request(rid))
        if str(cleared["schema_id"]) != str(self.schema_id):
            _fail("OTHER_SCHEMA")
        try:
            action, service, replicas = plan(cleared)
        except ValueError as err:
            _fail(str(err))
        except Exception:
            _fail("CLEARED_RECORD_UNREADABLE")
        if action == "scale":
            self.replicas = u256(replicas)
        else:
            self.last_service = service
        self.last_action = action
        self.log.append(json.dumps({"request": rid, "action": action, "service": service,
                                    "replicas": replicas}, sort_keys=True))
        self.executed[rid] = action

    @gl.public.view
    def status(self) -> str:
        return json.dumps({"replicas": int(self.replicas), "last_action": str(self.last_action),
                           "last_service": str(self.last_service),
                           "log": [str(x) for x in self.log],
                           "schema_id": str(self.schema_id)}, sort_keys=True)
