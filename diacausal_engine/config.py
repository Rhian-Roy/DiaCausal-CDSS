# diacausal_engine/config.py  (shim; removed in restructure step 9)
import importlib
import sys

sys.modules[__name__] = importlib.import_module("diacausal.config")
