import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.payment import CreditBalance, CheckoutSessionCreate, CheckoutSessionResponse
from app.config import get_settings

router = APIRouter()
settings = get_settings()

if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY

@router.get("/balance", response_model=CreditBalance)
def get_balance(current_user: User = Depends(get_current_user)):
    return {
        "credits": current_user.credits,
        "euros": current_user.credits / 100.0
    }

@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
def create_checkout_session(
    data: CheckoutSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe no está configurado")

    try:
        # Convert euros to cents for Stripe
        amount_cents = int(data.amount_euros * 100)
        
        if amount_cents < 100:
            raise HTTPException(status_code=400, detail="El importe mínimo es 1€")

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'eur',
                        'product_data': {
                            'name': f'Recarga de {data.amount_euros}€ en créditos',
                            'description': f'Equivale a {int(data.amount_euros * 100)} créditos para generación de vídeos',
                        },
                        'unit_amount': amount_cents,
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=f"{settings.FRONTEND_URL}/dashboard?payment=success",
            cancel_url=f"{settings.FRONTEND_URL}/dashboard?payment=cancel",
            client_reference_id=str(current_user.id),
            metadata={
                "user_id": str(current_user.id),
                "amount_credits": str(amount_cents)
            }
        )
        return {"checkout_url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    if not settings.STRIPE_WEBHOOK_SECRET:
        return {"status": "ignored", "reason": "No webhook secret configured"}

    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma inválida")

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('client_reference_id')
        
        if user_id:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                # amount_total is in cents
                amount_cents = session.get('amount_total', 0)
                user.credits += amount_cents
                db.commit()
                print(f"[PAYMENT] Added {amount_cents} credits to user {user_id}")

    return {"status": "success"}
