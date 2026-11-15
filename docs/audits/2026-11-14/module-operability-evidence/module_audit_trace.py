"""Audit-only call evidence. Records test IDs/function identifiers, never arguments or data."""
import json
import os
import sys
import threading
from pathlib import Path

_current = None
_calls = {}
_root = str(Path.cwd() / "src" / "pmc_api") + "/"

def _profile(frame, event, arg):
    if event != "call" or _current is None:
        return
    code = frame.f_code
    if not code.co_filename.startswith(_root):
        return
    key = code.co_filename[len(_root):] + ":" + code.co_qualname
    _calls.setdefault(key, set()).add(_current)

def pytest_sessionstart(session):
    sys.setprofile(_profile)
    threading.setprofile(_profile)

def pytest_runtest_setup(item):
    global _current
    _current = item.nodeid

def pytest_runtest_logfinish(nodeid, location):
    global _current
    _current = None

def pytest_sessionfinish(session, exitstatus):
    sys.setprofile(None)
    threading.setprofile(None)
    Path(os.environ["PMC_AUDIT_TRACE_OUTPUT"]).write_text(json.dumps({"scope": "actual Python function calls during test setup/call/teardown; arguments are not recorded; calls alone are not assertions", "calls": {key: sorted(ids) for key, ids in sorted(_calls.items())}}, indent=2) + "\n")
