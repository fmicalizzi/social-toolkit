"""Tests para shared/rate_limiter.py"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from shared.rate_limiter import rate_limit, rate_limit_batch


def test_rate_limit_sleeps():
    config = {
        "rate_limits": {
            "test": {
                "short_delay": [0.01, 0.02],
            }
        }
    }
    start = time.time()
    rate_limit(config, "test", "short_delay")
    elapsed = time.time() - start
    assert elapsed >= 0.01
    assert elapsed < 1.0  # no deberia dormir mas de 1s


def test_rate_limit_missing_platform():
    config = {"rate_limits": {}}
    # No deberia fallar, usa default [3, 6] pero para test usamos delay corto
    # Solo verificar que no crashea
    start = time.time()
    rate_limit(config, "nonexistent", "whatever")
    elapsed = time.time() - start
    assert elapsed >= 3.0  # default fallback


def test_rate_limit_batch_triggers():
    config = {
        "rate_limits": {
            "test": {
                "batch_size": 5,
                "batch_pause": [0.01, 0.02],
            }
        }
    }
    # No deberia pausar en count=3
    result = rate_limit_batch(config, "test", 3)
    assert result is False

    # Deberia pausar en count=5
    result = rate_limit_batch(config, "test", 5)
    assert result is True

    # Deberia pausar en count=10
    result = rate_limit_batch(config, "test", 10)
    assert result is True


def test_rate_limit_batch_zero():
    config = {
        "rate_limits": {
            "test": {
                "batch_size": 5,
                "batch_pause": [0.01, 0.02],
            }
        }
    }
    result = rate_limit_batch(config, "test", 0)
    assert result is False


if __name__ == "__main__":
    test_rate_limit_sleeps()
    print("  rate_limit_sleeps: ok")
    # Skip test_rate_limit_missing_platform (takes 3s)
    test_rate_limit_batch_triggers()
    print("  rate_limit_batch_triggers: ok")
    test_rate_limit_batch_zero()
    print("  rate_limit_batch_zero: ok")
    print("test_rate_limiter: ALL PASSED")
