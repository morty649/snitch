"""Phase 4 tests: verified kill loop. Offline only (FakeLLM), no network."""
from pathlib import Path

from snitch.kill import write_killer_tests
from snitch.llm import FakeLLM
from snitch.models import Mutant, MutantResult, Status
from snitch.runner import DEFAULT_TEST_CMD

DEMO = Path(__file__).resolve().parents[1] / "examples" / "shopcalc"


def _survivor() -> MutantResult:
    src = (DEMO / "shopcalc" / "pricing.py").read_text()
    ln = next(i for i, l in enumerate(src.splitlines(), 1) if "if quantity >= 10:" in l)
    m = Mutant("s10", "shopcalc/pricing.py", ln, "if quantity >= 10:", "if quantity > 10:")
    return MutantResult(m, Status.SURVIVED)


GOOD = """```python
from shopcalc.pricing import bulk_discount
def test_snitch_ten():
    assert bulk_discount(10) == 0.10
```
"""


def test_correct_killer_verified_and_kept():
    r = _survivor()
    fake = FakeLLM(lambda s, u: GOOD)
    assert write_killer_tests(fake, DEMO, [r], DEFAULT_TEST_CMD, 60.0) == 1
    assert r.killer_test and "def test_" in r.killer_test


def test_failing_on_original_rejected():
    r = _survivor()
    bad = "```python\nfrom shopcalc.pricing import bulk_discount\ndef test_snitch_x():\n    assert bulk_discount(10) == 0.99\n```\n"
    fake = FakeLLM(lambda s, u: bad)
    assert write_killer_tests(fake, DEMO, [r], DEFAULT_TEST_CMD, 60.0) == 0
    assert r.killer_test is None


def test_passing_on_both_rejected():
    r = _survivor()
    weak = "```python\nfrom shopcalc.pricing import bulk_discount\ndef test_snitch_x():\n    assert bulk_discount(1) == 0.0\n```\n"
    fake = FakeLLM(lambda s, u: weak)
    assert write_killer_tests(fake, DEMO, [r], DEFAULT_TEST_CMD, 60.0) == 0
    assert r.killer_test is None


def test_non_survivor_never_calls_llm():
    src = (DEMO / "shopcalc" / "pricing.py").read_text()
    ln = next(i for i, l in enumerate(src.splitlines(), 1) if "if quantity >= 10:" in l)
    m = Mutant("k", "shopcalc/pricing.py", ln, "if quantity >= 10:", "if quantity > 10:")
    r = MutantResult(m, Status.KILLED)
    fake = FakeLLM(lambda s, u: GOOD)
    assert write_killer_tests(fake, DEMO, [r], DEFAULT_TEST_CMD, 60.0) == 0
    assert len(fake.calls) == 0
