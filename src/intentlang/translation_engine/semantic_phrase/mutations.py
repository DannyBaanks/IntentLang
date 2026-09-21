"""
M5 — Mutation Harness: verifies the system catches intentionally incorrect translations.

Creates mutations of source phrases and verifies that the verifier REJECTS them.
If the harness doesn't kill mutants, the milestone is NOT PASS.

Usage:
    from semantic_phrase.mutations import run_mutation_harness, MutationResult
"""
from __future__ import annotations

from dataclasses import dataclass, field

from intentlang.translation_engine.semantic_phrase.extractor import extract_semantics
from intentlang.translation_engine.semantic_phrase.phrase_ir import PhraseStatus
from intentlang.translation_engine.semantic_phrase.verifier import VerifyResult, verify_roundtrip


@dataclass
class Mutation:
    """A single intentional mutation."""
    name: str
    description: str
    source: str
    mutated: str
    expected_detection: str  # field that should fail
    category: str


@dataclass
class MutationTest:
    """Result of testing a single mutation."""
    mutation: Mutation
    result: VerifyResult
    detected: bool
    detection_field: str | None = None


@dataclass
class MutationResult:
    """Complete mutation harness result."""
    total_mutations: int
    detected: int
    missed: int
    pass_rate: float
    tests: list[MutationTest] = field(default_factory=list)
    all_passed: bool = False

    def to_dict(self) -> dict:
        return {
            "total_mutations": self.total_mutations,
            "detected": self.detected,
            "missed": self.missed,
            "pass_rate": round(self.pass_rate, 3),
            "all_passed": self.all_passed,
            "tests": [
                {
                    "name": t.mutation.name,
                    "description": t.mutation.description,
                    "detected": t.detected,
                    "detection_field": t.detection_field,
                    "verdict": t.result.verdict,
                }
                for t in self.tests
            ],
        }


# ── Mutation Catalog ─────────────────────────────────────────────────

def build_mutation_catalog() -> list[Mutation]:
    """Build the catalog of mutations to test."""
    return [
        Mutation(
            name="remove_negation",
            description="Remove negation from a negative phrase",
            source="Do not delete this file",
            mutated="Delete this file",
            expected_detection="negation",
            category="negation",
        ),
        Mutation(
            name="change_modality",
            description="Change modal strength from must to may",
            source="You must save your changes before closing",
            mutated="You may save your changes before closing",
            expected_detection="modality",
            category="modality",
        ),
        Mutation(
            name="lose_placeholder",
            description="Remove a placeholder from the phrase",
            source="You have {count} unsaved changes",
            mutated="You have unsaved changes",
            expected_detection="slots",
            category="placeholder",
        ),
        Mutation(
            name="change_number",
            description="Change a numeric quantity",
            source="Delete 10 files permanently",
            mutated="Delete 100 files permanently",
            expected_detection="numbers",
            category="number",
        ),
        Mutation(
            name="change_destructive_action",
            description="Change destructive action to non-destructive",
            source="This will permanently delete your account",
            mutated="This will archive your account",
            expected_detection="destructive",
            category="destructive",
        ),
        Mutation(
            name="omit_consequence",
            description="Remove the consequence from a warning",
            source="Closing this workspace will discard all unsaved changes",
            mutated="Closing this workspace is possible",
            expected_detection="consequences",
            category="consequence",
        ),
        Mutation(
            name="invert_condition",
            description="Invert a conditional statement",
            source="If enabled, data will be synced automatically",
            mutated="If disabled, data will be synced automatically",
            expected_detection="conditions",
            category="condition",
        ),
        Mutation(
            name="change_shortcut",
            description="Change a keyboard shortcut",
            source="Press Ctrl+K to open the command palette",
            mutated="Press Ctrl+J to open the command palette",
            expected_detection="protected_tokens",
            category="shortcut",
        ),
        Mutation(
            name="change_technical_term",
            description="Change a technical term",
            source="This API endpoint returns JSON data",
            mutated="This API endpoint returns XML data",
            expected_detection="technical_terms",
            category="technical",
        ),
        Mutation(
            name="soften_warning",
            description="Weaken a warning's modality",
            source="Warning: This action will permanently delete all data",
            mutated="Note: This action might hide some data",
            expected_detection="modality",
            category="modality",
        ),
        Mutation(
            name="invert_polarity",
            description="Change negative phrase to positive",
            source="You cannot undo this deletion",
            mutated="You can easily restore this deletion",
            expected_detection="polarity",
            category="polarity",
        ),
        Mutation(
            name="change_speech_act",
            description="Change warning to notification",
            source="Warning: Unsaved changes will be lost",
            mutated="Info: Your changes have been saved",
            expected_detection="speech_act",
            category="speech_act",
        ),
    ]


def _detect_mutation(result: VerifyResult, mutation: Mutation) -> tuple[bool, str | None]:
    """Check if a mutation was detected by the verifier."""
    if result.verdict in (PhraseStatus.REJECTED.value, PhraseStatus.NEEDS_REVIEW.value):
        # Find which check failed
        for check in result.checks:
            if not check.passed:
                return True, check.field
        # Even if no specific check failed, the verdict is not VERIFIED
        return True, "verdict"

    return False, None


def run_mutation_harness() -> MutationResult:
    """Run the complete mutation harness.

    Tests that all intentional mutations are caught by the verifier.
    """
    mutations = build_mutation_catalog()
    tests = []
    detected = 0
    missed = 0

    for mutation in mutations:
        # Extract semantics from source
        source_extracted = extract_semantics(mutation.source)
        target_extracted = extract_semantics(mutation.mutated)

        # Verify roundtrip (source -> mutated should fail)
        result = verify_roundtrip(
            source=mutation.source,
            target=mutation.mutated,
            source_extracted=source_extracted,
            target_extracted=target_extracted,
        )

        # Check if mutation was detected
        was_detected, field = _detect_mutation(result, mutation)

        test = MutationTest(
            mutation=mutation,
            result=result,
            detected=was_detected,
            detection_field=field,
        )
        tests.append(test)

        if was_detected:
            detected += 1
        else:
            missed += 1

    total = len(mutations)
    pass_rate = detected / total if total > 0 else 0.0

    return MutationResult(
        total_mutations=total,
        detected=detected,
        missed=missed,
        pass_rate=pass_rate,
        tests=tests,
        all_passed=(missed == 0),
    )


def format_mutation_result(result: MutationResult) -> str:
    """Format mutation result for display."""
    lines = [
        "=== Mutation Harness ===",
        f"Total mutations: {result.total_mutations}",
        f"Detected: {result.detected}",
        f"Missed: {result.missed}",
        f"Pass rate: {result.pass_rate * 100:.1f}%",
        "",
    ]

    if result.all_passed:
        lines.append("STATUS: PASS — all mutations detected")
    else:
        lines.append(f"STATUS: FAIL — {result.missed} mutations missed")

    lines.append("")
    lines.append("=== Mutation Details ===")
    for test in result.tests:
        status = "DETECTED" if test.detected else "MISSED"
        lines.append(f"  [{status}] {test.mutation.name}")
        lines.append(f"    Source:     \"{test.mutation.source}\"")
        lines.append(f"    Mutated:    \"{test.mutation.mutated}\"")
        lines.append(f"    Verdict:    {test.result.verdict}")
        if test.detection_field:
            lines.append(f"    Field:      {test.detection_field}")
        lines.append("")

    return "\n".join(lines)
