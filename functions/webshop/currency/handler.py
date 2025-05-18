# functions/webshop/currency/handler.py

EUR_RATES = {
    "EUR": 1.0,
    "CAD": 1.5231,
    "HKD": 8.3693,
    "ISK": 157.5,
    "PHP": 54.778,
    "DKK": 7.4576,
    "HUF": 354.7,
    "CZK": 27.589,
    "AUD": 1.6805,
    "RON": 4.84,
    "SEK": 10.6695,
    "IDR": 16127.82,
    "INR": 81.9885,
    "BRL": 6.3172,
    "RUB": 79.6208,
    "HRK": 7.5693,
    "JPY": 115.53,
    "THB": 34.656,
    "CHF": 1.0513,
    "SGD": 1.5397,
    "PLN": 4.565,
    "BGN": 1.9558,
    "TRY": 7.4689,
    "CNY": 7.6759,
    "NOK": 11.0568,
    "NZD": 1.8145,
    "ZAR": 20.0761,
    "USD": 1.0798,
    "MXN": 25.8966,
    "ILS": 3.8178,
    "GBP": 0.88738,
    "KRW": 1332.6,
    "MYR": 4.6982,
}


async def handler(event, context=None, call_function=None):
    print("[currency] Eingabe:", event)

    from_curr = event["from"]["currencyCode"]
    to_curr = event["toCode"]
    units = event["from"]["units"]
    nanos = event["from"]["nanos"]

    rate = get_rate(from_curr, to_curr)
    conv_units, conv_nanos = apply_rate(units, nanos, rate)

    return {
        "units": conv_units,
        "nanos": conv_nanos,
        "currencyCode": to_curr
    }


def get_rate(from_curr, to_curr):
    return EUR_RATES[to_curr] / EUR_RATES[from_curr]


def symmetric_floor(value):
    return int(value) if value >= 0 else int(value) - 1


def apply_rate(units, nanos, rate):
    raw_units = units * rate
    new_units = symmetric_floor(raw_units)

    added_nanos = (raw_units - new_units) * 1e9
    new_nanos = symmetric_floor(nanos * rate + added_nanos)

    added_units = symmetric_floor(new_nanos / 999_999_999)
    final_units = new_units + added_units
    final_nanos = symmetric_floor(new_nanos % 999_999_999)

    return final_units, final_nanos

