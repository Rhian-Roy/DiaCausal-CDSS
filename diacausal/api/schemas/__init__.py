"""API v1 contract (plan 8.4): Pydantic v2 models, schema_version "1.0", unknown fields rejected.
The models generate openapi.json (scripts/export_openapi.py), which generates web/types.d.ts
(scripts/make_types.sh); tests/contract validates every example.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised
clinical use.
"""

from diacausal.api.schemas.base import OPTION_NAMES, SCHEMA_VERSION, OptionName, V1
from diacausal.api.schemas.card import (AbstainNoticeV1, AnswerCardV1, CardClaimV1, CitationV1, EffectRowV1,
                                        EvidenceLevelV1)
from diacausal.api.schemas.causal import CausalOutputV1, DriverV1, OptionV1
from diacausal.api.schemas.evidence import EvidenceBundleV1, EvidenceChunkV1, ScoresV1
from diacausal.api.schemas.guards import EligibleOptionsV1, GuardCheckV1, GuardResultV1, RuleHitV1
from diacausal.api.schemas.llm import AnswerDraftV1, ClaimV1, GuardedDraftV1, LLMRequestV1, OutputCheckV1
from diacausal.api.schemas.patient import RANGES, AskRequestV1, PatientV1, RecommendRequestV1, to_engine_patient
from diacausal.api.schemas.service import ErrorV1, HealthV1

# The twelve models named in P09, each with a JSON example in tests/contract/examples/<ModelName>.json
MODELS = {m.__name__: m for m in (PatientV1, AskRequestV1, GuardResultV1, EligibleOptionsV1, CausalOutputV1, DriverV1,
                                  EvidenceChunkV1, EvidenceBundleV1, LLMRequestV1, AnswerDraftV1, GuardedDraftV1, AnswerCardV1)}
