def add_one(event: dict) -> dict:
    """
    Erhöht den Wert im Event-Dictionary um 1.
    Erwartet: {"value": <int>}
    """
    input_value = event.get("value", 0)
    result = input_value + 1
    return {"value": result}


def square(event: dict) -> dict:
    """
    Quadriert den Wert im Event-Dictionary.
    Erwartet: {"value": <int>}
    """
    input_value = event.get("value", 0)
    result = input_value ** 2
    return {"value": result}
