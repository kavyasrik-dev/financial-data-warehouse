from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


CARD_FIELDS = [
    "card_id",
    "customer_id",
    "card_number",
    "card_type",
    "expiry_date",
    "card_status",
]
TRANSACTION_FIELDS = [
    "transaction_id",
    "customer_id",
    "card_id",
    "transaction_timestamp",
    "amount",
    "currency",
    "merchant_name",
    "merchant_category",
    "transaction_type",
    "transaction_status",
]

CARD_TYPES = ["debit", "credit", "prepaid"]
CARD_STATUSES = ["active", "blocked", "expired"]
CURRENCIES = ["USD", "INR", "GBP"]
TRANSACTION_TYPES = ["payment", "refund", "transfer"]
TRANSACTION_STATUSES = ["success", "failed", "pending"]
MERCHANTS = [
    ("Amazon", "ecommerce"),
    ("Apple", "electronics"),
    ("Big Basket", "grocery"),
    ("BookMyShow", "entertainment"),
    ("Netflix", "subscription"),
    ("Shell", "fuel"),
    ("Starbucks", "food_and_beverage"),
    ("Uber", "transport"),
    ("Walmart", "retail"),
    ("Zomato", "food_delivery"),
]


def parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def random_date(rng: random.Random, start: datetime, end: datetime) -> datetime:
    seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randint(0, max(seconds, 0)))


def luhn_check_digit(number: str) -> str:
    total = 0
    for index, char in enumerate(reversed(number + "0")):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - total % 10) % 10)


def card_number(rng: random.Random) -> str:
    prefix = rng.choice(["4532", "5424", "6011"])
    body = prefix + "".join(str(rng.randint(0, 9)) for _ in range(11))
    return body + luhn_check_digit(body)


def load_latest_customers(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Customer file not found: {path}")

    latest: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            customer_id = row["customer_id"]
            if customer_id not in latest or parse_date(row["created_at"]) > parse_date(latest[customer_id]["created_at"]):
                latest[customer_id] = row
    return sorted(latest.values(), key=lambda row: row["customer_id"])


def generate_cards(
    customers: list[dict[str, str]],
    rng: random.Random,
    secondary_card_rate: float,
    as_of: datetime,
) -> list[dict[str, str]]:
    cards = []
    used_numbers = set()

    for customer_index, customer in enumerate(customers, start=1):
        card_count = 1 + int(rng.random() < secondary_card_rate)
        for card_index in range(1, card_count + 1):
            number = card_number(rng)
            while number in used_numbers:
                number = card_number(rng)
            used_numbers.add(number)

            expires = as_of.date().replace(year=as_of.year + rng.randint(1, 5))
            cards.append(
                {
                    "card_id": f"CARD{customer_index:06d}{card_index}",
                    "customer_id": customer["customer_id"],
                    "card_number": number,
                    "card_type": rng.choices(CARD_TYPES, weights=[50, 45, 5], k=1)[0],
                    "expiry_date": expires.isoformat(),
                    "card_status": rng.choices(CARD_STATUSES, weights=[94, 4, 2], k=1)[0],
                }
            )
    return cards


def generate_transactions(
    cards: list[dict[str, str]],
    customers_by_id: dict[str, dict[str, str]],
    count: int,
    rng: random.Random,
    end: datetime,
) -> list[dict[str, str]]:
    if count < 1:
        raise ValueError("transaction count must be at least 1")

    rows = []
    for index in range(1, count + 1):
        card = rng.choice(cards)
        customer = customers_by_id[card["customer_id"]]
        start = parse_date(customer["created_at"])
        timestamp = random_date(rng, start, end)
        merchant_name, merchant_category = rng.choice(MERCHANTS)
        currency = "INR" if customer["country"] == "India" else rng.choice(CURRENCIES)
        transaction_type = rng.choices(TRANSACTION_TYPES, weights=[88, 8, 4], k=1)[0]
        amount = round(rng.uniform(5, 5_000), 2)

        rows.append(
            {
                "transaction_id": f"TXN{index:010d}",
                "customer_id": card["customer_id"],
                "card_id": card["card_id"],
                "transaction_timestamp": timestamp.isoformat(),
                "amount": f"{amount:.2f}",
                "currency": currency,
                "merchant_name": merchant_name,
                "merchant_category": merchant_category,
                "transaction_type": transaction_type,
                "transaction_status": rng.choices(TRANSACTION_STATUSES, weights=[93, 5, 2], k=1)[0],
            }
        )
    return sorted(rows, key=lambda row: (row["transaction_timestamp"], row["transaction_id"]))


def write_csv(rows: list[dict[str, str]], fields: list[str], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(
    customer_file: Path,
    cards_output: Path,
    transactions_output: Path,
    transaction_count: int,
    secondary_card_rate: float,
    seed: int,
    end: datetime,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if not 0 <= secondary_card_rate <= 1:
        raise ValueError("secondary-card-rate must be between 0 and 1")

    customers = load_latest_customers(customer_file)
    if not customers:
        raise ValueError("customer file has no rows")

    rng = random.Random(seed)
    cards = generate_cards(customers, rng, secondary_card_rate, end)
    transactions = generate_transactions(
        cards=cards,
        customers_by_id={row["customer_id"]: row for row in customers},
        count=transaction_count,
        rng=rng,
        end=end,
    )

    write_csv(cards, CARD_FIELDS, cards_output)
    write_csv(transactions, TRANSACTION_FIELDS, transactions_output)
    return cards, transactions


def self_check() -> None:
    rng = random.Random(7)
    customers = [
        {"customer_id": "C000001", "country": "India", "created_at": "2025-01-01T00:00:00+00:00"},
        {"customer_id": "C000002", "country": "USA", "created_at": "2025-02-01T00:00:00+00:00"},
    ]
    cards = generate_cards(customers, rng, secondary_card_rate=1, as_of=parse_date("2026-01-01"))
    transactions = generate_transactions(
        cards=cards,
        customers_by_id={row["customer_id"]: row for row in customers},
        count=10,
        rng=rng,
        end=parse_date("2026-01-01"),
    )
    assert len(cards) == 4
    assert len({row["card_number"] for row in cards}) == 4
    assert all(len(row["card_number"]) == 16 for row in cards)
    assert set(cards[0]) == set(CARD_FIELDS)
    assert len(transactions) == 10
    assert set(transactions[0]) == set(TRANSACTION_FIELDS)
    assert all(float(row["amount"]) > 0 for row in transactions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate realistic card and transaction CSV data.")
    parser.add_argument("--customers", default="data/customers/customers.csv", help="Customer CSV from Day 4.")
    parser.add_argument("--cards-output", default="data/cards/cards.csv", help="Output card CSV path.")
    parser.add_argument("--transactions-output", default="data/transactions/transactions.csv", help="Output transaction CSV path.")
    parser.add_argument("--transactions", type=int, default=5_000, help="Number of transactions to generate.")
    parser.add_argument("--secondary-card-rate", type=float, default=0.25, help="Share of customers with a second card.")
    parser.add_argument("--seed", type=int, default=84, help="Seed for repeatable output.")
    parser.add_argument("--end-date", default="2026-01-01", help="Inclusive ISO end date.")
    parser.add_argument("--self-check", action="store_true", help="Run generator assertions and exit.")
    args = parser.parse_args()

    if args.self_check:
        self_check()
        return

    cards, transactions = run(
        customer_file=Path(args.customers),
        cards_output=Path(args.cards_output),
        transactions_output=Path(args.transactions_output),
        transaction_count=args.transactions,
        secondary_card_rate=args.secondary_card_rate,
        seed=args.seed,
        end=parse_date(args.end_date),
    )
    print(f"Wrote {len(cards)} cards to {args.cards_output}")
    print(f"Wrote {len(transactions)} transactions to {args.transactions_output}")


if __name__ == "__main__":
    main()
