"""Creates CareerFit's products, prices and customer-portal settings in Stripe. Safe to run again.

Usage: python -m scripts.stripe_setup
Reads STRIPE_SECRET_KEY from apps/api/.env and only runs with a test-mode key; the key is never printed.
Prices are found later by their lookup keys, so no Stripe ids need to be copied into settings.
"""

import sys

import stripe

from app.billing import PORTAL_METADATA, PRO_PRICE_KEY, REPORT_PRICE_KEY
from app.config import settings

CURRENCY = "cad"
PRODUCTS = [
    {
        "lookup_key": PRO_PRICE_KEY,
        "name": "CareerFit Pro",
        "description": "Unlimited analyses, your resume rewritten for each job, and progress over time.",
        "unit_amount": 499,
        "recurring": {"interval": "month"},
    },
    {
        "lookup_key": REPORT_PRICE_KEY,
        "name": "CareerFit detailed report",
        "description": "A polished PDF of one result: score, skills, pay and your 30/60/90-day plan.",
        "unit_amount": 299,
        "recurring": None,
    },
]


def ensure_price(client: stripe.StripeClient, spec: dict[str, object]) -> str:
    lookup_key = str(spec["lookup_key"])
    found = client.v1.prices.list({"lookup_keys": [lookup_key], "active": True, "limit": 1})
    if found.data:
        return f"{lookup_key}: already there"
    product = client.v1.products.create(
        {
            "name": str(spec["name"]),
            "description": str(spec["description"]),
            "metadata": {"app": "careerfit"},
        }
    )
    params: dict[str, object] = {
        "product": product.id,
        "currency": CURRENCY,
        "unit_amount": spec["unit_amount"],
        "lookup_key": lookup_key,
    }
    if spec["recurring"]:
        params["recurring"] = spec["recurring"]
    client.v1.prices.create(params)  # type: ignore[arg-type]
    amount = int(str(spec["unit_amount"])) / 100
    return f"{lookup_key}: created at {amount:.2f} {CURRENCY.upper()}"


def ensure_portal(client: stripe.StripeClient) -> str:
    for configuration in client.v1.billing_portal.configurations.list({"active": True, "limit": 100}).data:
        if (configuration.to_dict().get("metadata") or {}).get("app") == PORTAL_METADATA["app"]:
            return "customer portal: already set up"
    client.v1.billing_portal.configurations.create(
        {
            "business_profile": {"headline": "Manage your CareerFit plan"},
            "features": {
                # People keep Pro until the end of the month they paid for.
                "subscription_cancel": {
                    "enabled": True,
                    "mode": "at_period_end",
                    "cancellation_reason": {
                        "enabled": True,
                        "options": ["too_expensive", "unused", "missing_features", "other"],
                    },
                },
                "payment_method_update": {"enabled": True},
                "invoice_history": {"enabled": True},
                "customer_update": {"enabled": False},
                "subscription_update": {"enabled": False},
                "subscription_pause": {"enabled": False},
            },
            "metadata": dict(PORTAL_METADATA),
        }
    )
    return "customer portal: created"


def main() -> None:
    key = settings.stripe_secret_key
    if not key.startswith(("sk_test_", "rk_test_")):
        sys.exit("STRIPE_SECRET_KEY in apps/api/.env must be a test-mode key (sk_test_...).")
    client = stripe.StripeClient(key)
    for spec in PRODUCTS:
        print(ensure_price(client, spec))
    print(ensure_portal(client))


if __name__ == "__main__":
    main()
