import random
import asyncio

def jitter(min_s: float, max_s: float) -> float:
    return random.uniform(min_s, max_s)

async def sleep_jitter(min_s: float, max_s: float):
    await asyncio.sleep(jitter(min_s, max_s))
