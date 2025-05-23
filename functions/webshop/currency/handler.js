// This is not called directly by AWS but by the Fusion Handler inside the lambda
// callFunction is a function that expects three parameters: The Function to Call, the parameters to pass, and whether the result is sync. It returns a promise that *must* be await-ed
exports.handler = async function (event, callFunction) {
    console.log("currency", event)

    const rate = getRate(event.from.currencyCode, event.toCode)
    const [convUnits, convNanos] = applyRate(event.from.units, event.from.nanos, rate)
  
    // carry over fractions from units
    return { units: convUnits, nanos: convNanos, currencyCode: event.toCode }
}

// Below here is directly from Befaas - its awesome
const EUR_RATES = {
    EUR: 1.0,
    CAD: 1.5231,
    HKD: 8.3693,
    ISK: 157.5,
    PHP: 54.778,
    DKK: 7.4576,
    HUF: 354.7,
    CZK: 27.589,
    AUD: 1.6805,
    RON: 4.84,
    SEK: 10.6695,
    IDR: 16127.82,
    INR: 81.9885,
    BRL: 6.3172,
    RUB: 79.6208,
    HRK: 7.5693,
    JPY: 115.53,
    THB: 34.656,
    CHF: 1.0513,
    SGD: 1.5397,
    PLN: 4.565,
    BGN: 1.9558,
    TRY: 7.4689,
    CNY: 7.6759,
    NOK: 11.0568,
    NZD: 1.8145,
    ZAR: 20.0761,
    USD: 1.0798,
    MXN: 25.8966,
    ILS: 3.8178,
    GBP: 0.88738,
    KRW: 1332.6,
    MYR: 4.6982
}

function getRate(from, to) {
    return EUR_RATES[to] / EUR_RATES[from]
}

function symmetricFloor(amount) {
    if (amount > 0) {
        return Math.floor(amount)
    } else {
        return Math.ceil(amount)
    }
}

function applyRate(units, nanos, rate) {
    const rawUnits = units * rate
    const newUnits = symmetricFloor(rawUnits)

    const addedNanos = (rawUnits - newUnits) * 1e9
    const newNanos = symmetricFloor(nanos * rate + addedNanos)

    const addedUnits = symmetricFloor(newNanos / 999999999)

    const finalUnits = newUnits + addedUnits
    const finalNanos = symmetricFloor(newNanos % 999999999)

    return [finalUnits, finalNanos]
}