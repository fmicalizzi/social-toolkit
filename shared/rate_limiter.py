"""Rate limiting configurable con delays random y batch pauses."""

import time
import random


def rate_limit(config: dict, platform: str, delay_key: str):
    """Duerme un tiempo aleatorio segun config[rate_limits][platform][delay_key]."""
    limits = config.get("rate_limits", {}).get(platform, {})
    delay_range = limits.get(delay_key, [3, 6])
    delay = random.uniform(delay_range[0], delay_range[1])
    time.sleep(delay)


def rate_limit_batch(config: dict, platform: str, count: int) -> bool:
    """Si count es multiplo de batch_size, aplica batch_pause. Retorna True si pausó."""
    limits = config.get("rate_limits", {}).get(platform, {})
    batch_size = limits.get("batch_size", 50)
    if batch_size > 0 and count > 0 and count % batch_size == 0:
        pause_range = limits.get("batch_pause", [120, 180])
        pause = random.uniform(pause_range[0], pause_range[1])
        print(f"\n--- Pausa de batch ({pause:.0f}s) tras {count} items ---\n")
        time.sleep(pause)
        return True
    return False
