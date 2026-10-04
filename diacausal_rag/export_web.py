# diacausal_rag/export_web.py  (shim; removed in restructure step 9)
# `python -m diacausal_rag.export_web` still works: it forwards to main() of the new module.
import importlib
import sys

if __name__ == "__main__":
    importlib.import_module("diacausal.rag.export_web").main()
else:
    sys.modules[__name__] = importlib.import_module("diacausal.rag.export_web")
