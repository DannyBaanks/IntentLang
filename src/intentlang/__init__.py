"""intent-lang: lenguaje natural -> intención canonica -> programa ejecutable."""

from .cache import (
    CacheEntry,
    SignedAssistedCache,
    cached_assisted_resolve,
    get_assisted_cache,
)
from .capabilities import (
    execute_capability,
    get_capability_info,
    get_contract,
    list_capabilities,
    register_capability,
)
from .cobol_guard import CobolVerification, verify_cobol_round_trip
from .codegen import (
    PRIMITIVE_TO_LANG_OP,
    CodegenResult,
    generate_code,
    list_primitives_for_language,
    list_supported_languages,
    verify_codegen_compatibility,
)
from .complex_program import (
    Effect,
    PermissionError,
    ProgramPlan,
    ProgramTypeError,
    ValueType,
    check_program,
    parse_structured,
    plan_program,
    run_structured,
)
from .discovery import (
    DiscoveryEngine,
    discover,
    discover_from_unknown,
    enumerate_candidates,
    verify_candidate,
)
from .domain import (
    DOMAIN_PRIMITIVE_MAP,
    DOMAIN_TABLE,
    check_cross_lingual_convergence,
    resolve_with_domain,
    resolve_with_domain_table,
)
from .executor import ExecutionError, ReturnSignal, execute_program
from .ir import (
    PRIMITIVES,
    PRIMITIVES_CONTROL,
    PRIMITIVES_DATA,
    PRIMITIVES_EFFECTS,
    Concept,
    Intent,
    Provenance,
    Status,
)
from .lexicon import (
    LexiconUnavailable,
    UnsupportedLanguage,
    ensure_installed,
    senses,
    source_id,
    supported_languages,
    synonyms,
)
from .lowering import lower_intent_to_program, lower_text_to_program
from .malbolge_validator import (
    MalbolgeEvidence,
    MalbolgeValidator,
    get_malbolge_validator,
    validate_malbolge_pipeline,
)
from .normalize import tokens, verb_candidates
from .oracle import Execution, fingerprint, granularity_controls
from .parity import (
    ParityReport,
    SurfaceRun,
    parity_for_group,
    prove_domain_table,
    run_corpus_parity,
    run_surface,
    symbol_for_lemma,
)
from .portable_codegen import PortableCodegenError, PortableSource, generate_program_source
from .primitives import DECLARED_GAPS, MAX_ENTRIES, load_map, primitive_for
from .program import (
    Program,
    ProgramNode,
    bind,
    call,
    collect,
    compare,
    filter_,
    foreach,
    if_,
    let,
    load,
    loop,
    map_,
    ref,
    seq,
    store,
    transaction,
    try_,
    value,
)
from .propose import ProposalRecord, cache_key, propose, validate
from .relex import DECLARED_OPERAND_PASSTHROUGH, round_trip
from .resolve import resolve
from .semantic import (
    SemanticCapability,
    SemanticResult,
    SemanticRouter,
    SimilarityResult,
    WordNetSemantic,
    get_semantic_backend,
    get_semantic_router,
    list_supported_semantic_languages,
    lookup_semantic,
    register_semantic_backend,
    semantic_similarity,
)
from .transaction import execute_transaction

__all__ = [  # noqa: RUF022 - grouped by public subsystem for API readability
    "DECLARED_GAPS",
    "DECLARED_OPERAND_PASSTHROUGH",
    "DOMAIN_PRIMITIVE_MAP",
    # domain
    "DOMAIN_TABLE",
    "MAX_ENTRIES",
    # ir
    "PRIMITIVES",
    "PRIMITIVES_CONTROL",
    "PRIMITIVES_DATA",
    "PRIMITIVES_EFFECTS",
    "PRIMITIVE_TO_LANG_OP",
    # cache
    "CacheEntry",
    # codegen
    "CodegenResult",
    "CobolVerification",
    "Effect",
    "Concept",
    # discovery
    "DiscoveryEngine",
    "ExecutionError",
    "Intent",
    "LexiconUnavailable",
    "ParityReport",
    # malbolge
    "MalbolgeEvidence",
    "MalbolgeValidator",
    # program
    "Program",
    "ProgramNode",
    "ProgramPlan",
    "ProgramTypeError",
    "PortableCodegenError",
    "PortableSource",
    "PermissionError",
    "ProposalRecord",
    "Provenance",
    "ReturnSignal",
    # semantic
    "SemanticCapability",
    "SemanticResult",
    "SemanticRouter",
    "SignedAssistedCache",
    "SimilarityResult",
    "Status",
    "SurfaceRun",
    "UnsupportedLanguage",
    "ValueType",
    "WordNetSemantic",
    "bind",
    "cache_key",
    "check_program",
    "cached_assisted_resolve",
    "call",
    "check_cross_lingual_convergence",
    "collect",
    "compare",
    "discover",
    "discover_from_unknown",
    "ensure_installed",
    "enumerate_candidates",
    # capabilities
    "execute_capability",
    # executor
    "execute_program",
    "execute_transaction",
    "transaction",
    "filter_",
    "foreach",
    "generate_code",
    "generate_program_source",
    "verify_cobol_round_trip",
    "get_assisted_cache",
    "get_capability_info",
    "get_contract",
    "get_malbolge_validator",
    "get_semantic_backend",
    "get_semantic_router",
    "granularity_controls",
    # oracle / parity
    "Execution",
    "fingerprint",
    "if_",
    "let",
    "list_capabilities",
    "list_primitives_for_language",
    "list_supported_languages",
    "list_supported_semantic_languages",
    "load",
    # primitives
    "load_map",
    "lookup_semantic",
    "loop",
    "lower_intent_to_program",
    # lowering
    "lower_text_to_program",
    "map_",
    "primitive_for",
    "parse_structured",
    "parity_for_group",
    "plan_program",
    "prove_domain_table",
    # propose
    "propose",
    "register_capability",
    "register_semantic_backend",
    # resolve
    "resolve",
    "resolve_with_domain",
    "resolve_with_domain_table",
    "ref",
    # relex
    "round_trip",
    "run_corpus_parity",
    "run_structured",
    "run_surface",
    "semantic_similarity",
    "senses",
    "seq",
    "symbol_for_lemma",
    # lexicon
    "source_id",
    "store",
    "supported_languages",
    "synonyms",
    # normalize
    "tokens",
    "try_",
    "validate",
    "validate_malbolge_pipeline",
    "value",
    "verb_candidates",
    "verify_candidate",
    "verify_codegen_compatibility",
]
