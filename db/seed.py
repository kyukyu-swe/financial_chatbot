"""
Seed script: inserts 200 transactions (40 per merchant) into the SQLite DB.

Run directly:
    python -m db.seed
"""

import random
import math
import uuid
from datetime import datetime, timedelta

from db.database import SessionLocal, Transaction, init_db

MERCHANTS = ["mch_001", "mch_002", "mch_003", "mch_004", "mch_005"]
LOCATIONS = ["Bangkok", "Chiang Mai", "Phuket", "Singapore", "London"]
ERROR_CODES = ["401", "402", "422", "500"]

TOTAL = 200
PER_MERCHANT = TOTAL // len(MERCHANTS)   # 40 each
SUCCESS_RATE = 0.70
NOW = datetime(2026, 3, 15, 12, 0, 0)
LOOKBACK_DAYS = 30


def _random_amount(rng: random.Random) -> float:
    """Log-normal amount in THB 100 – 50 000."""
    mu = math.log(3000)
    sigma = 1.2
    while True:
        val = rng.lognormvariate(mu, sigma)
        if 100 <= val <= 50_000:
            return round(val, 2)


def _random_timestamp(rng: random.Random) -> datetime:
    offset_seconds = rng.randint(0, LOOKBACK_DAYS * 24 * 3600)
    return NOW - timedelta(seconds=offset_seconds)


def seed() -> None:
    init_db()

    rng = random.Random(42)
    db = SessionLocal()

    try:
        existing = db.query(Transaction).count()
        if existing >= TOTAL:
            print(f"Database already has {existing} transactions — skipping seed.")
            return

        rows: list[Transaction] = []
        for i, merchant_id in enumerate(MERCHANTS):
            location = LOCATIONS[i]
            for _ in range(PER_MERCHANT):
                is_success = rng.random() < SUCCESS_RATE
                status = "successful" if is_success else "failed"
                error_code = None if is_success else rng.choice(ERROR_CODES)

                rows.append(
                    Transaction(
                        transaction_id=str(uuid.UUID(int=rng.getrandbits(128))),
                        merchant_id=merchant_id,
                        amount=_random_amount(rng),
                        currency="THB",
                        status=status,
                        error_code=error_code,
                        location=location,
                        created_at=_random_timestamp(rng),
                    )
                )

        db.bulk_save_objects(rows)
        db.commit()
        print(f"Seeded {len(rows)} transactions across {len(MERCHANTS)} merchants.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
