"""Integration smoke for herdr-agent-ops against a live herdr session.

Does NOT start real agents (avoids spawning processes). Verifies:
- hao doctor passes
- cmd_name on a shell pane sets the hao- label (label-first behavior)
- restore --dry-run does not error
Cleans up the test pane it created.
"""
import json
import os
import types
from importlib.machinery import SourceFileLoader

_loader = SourceFileLoader("hao", os.path.join(os.path.dirname(__file__), "..", "..", "..", "herdr-agent-ops", "scripts", "hao"))
hao = types.ModuleType(_loader.name)
_loader.exec_module(hao)


def main():
    assert hao.cmd_doctor() == 0, "doctor should pass"

    # create a shell pane
    rc, out, _ = hao.run_herdr(["pane", "split", "--current", "--direction", "right", "--cwd", os.getcwd(), "--no-focus"])
    assert rc == 0, f"split failed: {out}"
    pane = json.loads(out)["result"]["pane"]["pane_id"]
    print("created test pane", pane)

    try:
        # name on shell pane: label set even though agent rename may fail (no agent)
        rc = hao.cmd_name(pane, "hawk", "api", False, False)
        rc2, out2, _ = hao.run_herdr(["pane", "get", pane])
        lbl = json.loads(out2)["result"]["pane"].get("label")
        assert lbl == "hao-hawk-api", f"label not set: {lbl} (rc={rc})"
        print("label set ok:", lbl)

        # restore dry-run must not error
        rc3 = hao.cmd_restore(os.environ.get("HERDR_WORKSPACE_ID", "w2"), False, True, True, None)
        assert rc3 in (0, 6), f"restore dry-run rc={rc3}"
        print("restore dry-run ok, rc:", rc3)
    finally:
        # close the test pane we created (safe: we created it)
        hao.run_herdr(["pane", "close", pane])
        print("closed test pane", pane)

    print("INTEGRATION OK")


if __name__ == "__main__":
    main()
