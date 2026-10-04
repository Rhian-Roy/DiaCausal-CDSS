# diacausal_rag/explain.py  (shim; removed in restructure step 9)
# Split into llm/explain.py, llm/prompt_builder.py, llm/providers/{template,ollama}.py and guards/output_guards.py, so the
# shim names what it re-exports. `python -m diacausal_rag.explain` still works: it forwards to main().
from diacausal.guards.output_guards import (  # noqa: F401
    _ANSWER_SPLIT, _BULLET, _CITES, _SPLIT, _content, _usable, check_answer, sentences,
)
from diacausal.llm.explain import BACKENDS, CALLERS, DOSE_QUESTION, NO_DOSE_NOTE, explain, main, render  # noqa: F401
from diacausal.llm.prompt_builder import PROMPT, build_prompt  # noqa: F401
from diacausal.llm.providers.ollama import _post, call_ollama  # noqa: F401
from diacausal.llm.providers.template import _reply, _weighted_overlap, template  # noqa: F401

if __name__ == "__main__":
    main()
