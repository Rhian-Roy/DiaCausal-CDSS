# diacausal_engine/metrics.py  (shim; removed in restructure step 9)
import importlib
import sys

sys.modules[__name__] = importlib.import_module("diacausal.causal_inference.metrics")
