"""S33 ml4t-live 0.1.3 check M7 and ml4t-data 0.3.1 check M8 (rules: PREREGISTERED.md). Offline, no connection.

Usage: python -I s33_ml4tlive_checks.py out.json   (M7 in the ml4t-live venv; M8 runs if ml4t-data is importable)
"""
import dataclasses
import inspect
import json
import sys

out = {}
try:
    from ml4t.live import IBBroker, LiveRiskConfig

    sig = inspect.signature(IBBroker.__init__)
    kwargs = {}
    b = IBBroker(**kwargs) if all(p.default is not inspect._empty or p.name == "self" or p.kind in (p.VAR_KEYWORD, p.VAR_POSITIONAL)
                                  for p in sig.parameters.values()) else None
    contract = b._get_contract("MBT") if b is not None else None
    defaults = {f.name: f.default for f in dataclasses.fields(LiveRiskConfig)
                if f.default is not dataclasses.MISSING}
    out["M7_live"] = {"ibbroker_init_params": list(sig.parameters)[1:],
                      "contract_for_MBT": repr(contract), "contract_type": type(contract).__name__ if contract else None,
                      "risk_defaults": {k: (v if isinstance(v, (int, float, bool, str, type(None))) else repr(v))
                                        for k, v in defaults.items()}}
except Exception as exc:
    out["M7_live"] = {"error": repr(exc)[:400]}

try:
    import pkgutil

    import ml4t.data.providers as prov

    names = sorted(m.name for m in pkgutil.iter_modules(prov.__path__))
    wanted = {"kraken": any("kraken" in n for n in names), "coinbase": any("coinbase" in n for n in names),
              "ibkr": any(n in ("ib", "ibkr", "interactive_brokers") or "ibkr" in n for n in names)}
    out["M8_data_providers"] = {"modules": names, "covers": wanted}
except Exception as exc:
    out["M8_data_providers"] = {"error": repr(exc)[:300]}

with open(sys.argv[1], "w") as fh:
    json.dump(out, fh, indent=2, default=str)
print(json.dumps(out, default=str)[:3000])
