# diacausal_rag/pdf_text.py  (shim; removed in restructure step 9)
# `python -m diacausal_rag.pdf_text` still works: it forwards to main() of the new module.
import importlib
import sys

if __name__ == "__main__":
    importlib.import_module("diacausal.rag.ingest.pdf_text").main()
else:
    sys.modules[__name__] = importlib.import_module("diacausal.rag.ingest.pdf_text")
