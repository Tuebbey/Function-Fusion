# functions/webshop/payment/handler.py

import secrets
import math

def eratosthenes(limit):
    primes = []
    if limit >= 2:
        nums = list(range(2, limit + 1))
        sqrt_limit = int(math.sqrt(limit)) + 1
        for i in range(sqrt_limit):
            p = nums[i]
            if p:
                for j in range(p * p - 2, len(nums), p):
                    nums[j] = 0
        primes = [p for p in nums if p]
    return primes

async def handler(event, context=None, call_function=None):
    print("[payment] Eingabe:", event)

    # CPU-intensive Berechnung simulieren
    eratosthenes(500_000)

    # Zufällige Transaktions-ID erzeugen
    transaction_id = secrets.token_hex(16)

    return {"transactionId": transaction_id}

