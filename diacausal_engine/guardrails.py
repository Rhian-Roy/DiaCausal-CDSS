# diacausal_engine/guardrails.py  (shim; removed in restructure step 9)
import importlib
import sys

sys.modules[__name__] = importlib.import_module("diacausal.guards.rules_loader")
