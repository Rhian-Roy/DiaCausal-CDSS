# diacausal_engine/benchmark.py  (shim; removed in restructure step 9)
# `python -m diacausal_engine.benchmark` still works: it forwards to main() of the new module.
import importlib
import sys

if __name__ == "__main__":
    importlib.import_module("diacausal.causal_inference.benchmark").main()
else:
    sys.modules[__name__] = importlib.import_module("diacausal.causal_inference.benchmark")
