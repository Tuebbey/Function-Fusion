# functions/webshop/shiporder/handler.py

import secrets
import math

def eratosthenes(limit):
    primes = []
    if limit >= 2:
        nums = list(range(2, limit + 1))
        sqrt_limit = int(math.sqrt(limit))
        for i in range(sqrt_limit):
            p = nums[i]
            if p:
                for j in range(p * p - 2, len(nums), p):
                    nums[j] = 0
        primes = [p for p in nums if p]
    return primes

async def handler(event, context=None, call_function=None):
    print("[shiporder] Eingabe:", event)
    eratosthenes(500_000)  # CPU-intensive Task zur Simulation
    return {
        "id": secrets.token_hex(16)  # Zufällige ID wie in JS mit crypto
    }


