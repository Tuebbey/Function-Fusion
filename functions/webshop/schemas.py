# functions/webshop/schemas.py
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

# Basisklassen für wiederverwendbare Strukturen
class Money(BaseModel):
    currencyCode: str
    units: int
    nanos: int = 0

class Address(BaseModel):
    streetAddress: str
    city: str
    state: str
    country: str

class CreditCard(BaseModel):
    creditCardNumber: str
    creditCardCvv: int
    creditCardExpirationYear: int
    creditCardExpirationMonth: int

class Product(BaseModel):
    id: str
    name: str
    description: str
    picture: str
    priceUsd: Money
    categories: List[str]

# Funktionsspezifische Klassen
class AddCartItem:
    class Request(BaseModel):
        userId: str
        productId: str
        quantity: int
    
    class Response(BaseModel):
        status: str
        response: Dict[str, Any]

class CartKvStorage:
    class AddRequest(BaseModel):
        operation: str = "add"
        userId: str
        item: Dict[str, Any]
    
    class GetRequest(BaseModel):
        operation: str = "get"
        userId: str
    
    class EmptyRequest(BaseModel):
        operation: str = "empty"
        userId: str
    
    class AddResponse(BaseModel):
        status: str
        userId: str
        item: Dict[str, Any]
        performance: Optional[Dict[str, Any]] = None
    
    class GetResponse(BaseModel):
        userId: str
        items: List[Dict[str, Any]]
        performance: Optional[Dict[str, Any]] = None

class Checkout:
    class Request(BaseModel):
        userId: str
        userCurrency: str
        address: Address
        email: str
        creditCard: CreditCard
    
    class Response(BaseModel):
        orderId: str
        shippingTrackingId: str
        shippingCost: Money
        shippingAddress: Address
        items: List[Dict[str, Any]]

class Currency:
    class Request(BaseModel):
        from_: Money = Field(..., alias="from")
        toCode: str
    
    class Response(BaseModel):
        units: int
        nanos: int
        currencyCode: str

class Email:
    class Request(BaseModel):
        message: str
        to: str
    
    class Response(BaseModel):
        success: bool

class EmptyCart:
    class Request(BaseModel):
        userId: str
    
    class Response(BaseModel):
        __root__: bool

class Frontend:
    class Request(BaseModel):
        operation: str = "get"
        userId: str = "0"
        currency: str = "USD"
    
    class CartRequest(BaseModel):
        operation: str = "cart"
        userId: str
    
    class CheckoutRequest(BaseModel):
        operation: str = "checkout"
        userId: str
        creditCardNumber: str
    
    class AddCartRequest(BaseModel):
        operation: str = "addcart"
        userId: str
        productId: str
        quantity: int = 1
    
    class Response(BaseModel):
        ads: List[Dict[str, Any]]
        supportedCurrencies: Dict[str, Any]
        recommendations: List[Dict[str, Any]]
        cart: List[Dict[str, Any]]
        productsList: List[Dict[str, Any]]

class GetAds:
    class Response(BaseModel):
        __root__: List[Dict[str, str]]

class GetCart:
    class Request(BaseModel):
        userId: str
    
    class Response(BaseModel):
        __root__: List[Dict[str, Any]]

class GetProduct:
    class Request(BaseModel):
        id: str
    
    class Response(BaseModel):
        id: str
        name: str
        description: str
        picture: str
        priceUsd: Money
        categories: List[str]

class ListProducts:
    class Response(BaseModel):
        products: List[Product]

class ListRecommendations:
    class Request(BaseModel):
        userId: str
        productIds: List[str]
    
    class Response(BaseModel):
        __root__: List[Dict[str, Any]]

class Payment:
    class Request(BaseModel):
        amount: Money
        creditCard: CreditCard
    
    class Response(BaseModel):
        transactionId: str

class SearchProducts:
    class Request(BaseModel):
        query: str
    
    class Response(BaseModel):
        results: List[Product]

class ShipmentQuote:
    class Request(BaseModel):
        userId: str
        items: List[Dict[str, Any]]
    
    class Response(BaseModel):
        costUsd: Money

class ShipOrder:
    class Request(BaseModel):
        address: Address
        items: List[Dict[str, Any]]
    
    class Response(BaseModel):
        id: str

class SupportedCurrencies:
    class Response(BaseModel):
        currencyCodes: List[str]