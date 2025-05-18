# functions/demo/demo.py

def add_one(event, call_function=None):
    print("[add_one] Eingabe:", event)
    value = event.get("value", 0)
    return {"value": value + 1}

def square(event, call_function=None):
    print("[square] Eingabe:", event)
    value = event.get("value", 0)
    return {"value": value * value}

