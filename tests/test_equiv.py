"""Phase 3 tests: equivalent-mutant filter. Offline only (FakeLLM), no network."""
from pathlib import Path

from snitch.equiv import flag_equivalents
from snitch.llm import FakeLLM
from snitch.models import Mutant, MutantResult, Status

DEMO = Path(__file__).resolve().parents[1] / "examples" / "shopcalc"
PRICING = "shopcalc/pricing.py"


def _survivor() -> MutantResult:
    src = (DEMO / PRICING).read_text()
    ln = next(i for i, l in enumerate(src.splitlines(), 1) if "if quantity >= 10:" in l)
    m = Mutant("s", PRICING, ln, "if quantity >= 10:", "if quantity > 10:")
    return MutantResult(m, Status.SURVIVED)


def _killed() -> MutantResult:
    src = (DEMO / PRICING).read_text()
    ln = next(i for i, l in enumerate(src.splitlines(), 1) if "if quantity >= 10:" in l)
    m = Mutant("k", PRICING, ln, "if quantity >= 10:", "if quantity > 10:")
    return MutantResult(m, Status.KILLED)


def test_equiv_true_flags_survivor():
    r = _survivor()
    fake = FakeLLM(lambda s, u: '{"equivalent": true, "witness_input": "", "reason": "same behavior"}')
    assert flag_equivalents(fake, DEMO, [r]) == 1
    assert r.mutant.likely_equivalent is True


def test_equiv_false_not_flagged():
    r = _survivor()
    fake = FakeLLM(lambda s, u: '{"equivalent": false, "witness_input": "quantity=10", "reason": "differs"}')
    assert flag_equivalents(fake, DEMO, [r]) == 0
    assert r.mutant.likely_equivalent is False


def test_killed_never_calls_llm():
    r = _killed()
    fake = FakeLLM(lambda s, u: '{"equivalent": true}')
    assert flag_equivalents(fake, DEMO, [r]) == 0
    assert len(fake.calls) == 0


def test_garbage_reply_not_flagged_no_crash():
    r = _survivor()
    fake = FakeLLM(lambda s, u: "I think so")
    assert flag_equivalents(fake, DEMO, [r]) == 0
    assert r.mutant.likely_equivalent is False
