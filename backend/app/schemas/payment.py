from pydantic import BaseModel

class CreditBalance(BaseModel):
    credits: int
    euros: float

class CheckoutSessionCreate(BaseModel):
    amount_euros: float

class CheckoutSessionResponse(BaseModel):
    checkout_url: str
