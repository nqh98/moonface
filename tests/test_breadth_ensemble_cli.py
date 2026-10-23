import importlib.util
import json
import sys
from pathlib import Path

import tools.breadth.breadth as _tools_breadth

ROOT = Path(__file__).resolve().parents[1]

# The CLI does `from breadth import ...`. Pytest's prepend collection caches the
# bare name `breadth` as the tests/research/breadth/ test package; point `breadth`
# at tools/breadth.py for the CLI load, then restore the prior binding.
_saved = sys.modules.get("breadth")
sys.modules["breadth"] = _tools_breadth
try:
    spec = importlib.util.spec_from_file_location(
        "breadth_ensemble", ROOT / "tools" / "breadth" / "breadth_ensemble.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
finally:
    if _saved is not None:
        sys.modules["breadth"] = _saved
    else:
        sys.modules.pop("breadth", None)


def _result(tmp_path, keys):
    doc = {"windows": {"sealed": [100, 999]},
           "rows": [{"verdict": "forward_candidate",
                     "spec": {"key": k, "builder": k, "params": {},
                              "exit_name": "atr_trail", "exit_params": {}, "h": 48}}
                    for k in keys]}
    p = tmp_path / f"RESULT_{'_'.join(keys)}.json"
    p.write_text(json.dumps(doc))
    return str(p)


def test_register_writes_forward_registration(tmp_path):
    r = _result(tmp_path, ["breadth_thrust", "net_new_highs"])
    out = tmp_path / "out"
    rc = cli.run(["--register", "--result", r, "--start-ms", "0",
                  "--end-ms", "1", "--out-dir", str(out)])
    assert rc == 0
    reg = json.loads((out / "PREREGISTRATION.json").read_text())
    assert reg["member_keys"] == ["breadth_thrust", "net_new_highs"]
    assert reg["t0"] == 999
    assert (out / "ENSEMBLE_FORWARD_REGISTRATION.md").exists()


def test_register_insufficient_members(tmp_path):
    r = _result(tmp_path, ["only_one"])
    out = tmp_path / "out"
    rc = cli.run(["--register", "--result", r, "--start-ms", "0",
                  "--end-ms", "1", "--out-dir", str(out)])
    assert rc == 0
    reg = json.loads((out / "PREREGISTRATION.json").read_text())
    assert reg["status"] == "insufficient_members"
    assert not (out / "ENSEMBLE_FORWARD_REGISTRATION.md").exists()
