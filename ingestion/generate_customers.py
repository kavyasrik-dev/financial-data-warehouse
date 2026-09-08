from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


FIELDS = [
    "customer_id",
    "customer_name",
    "email",
    "phone",
    "address",
    "city",
    "state",
    "country",
    "customer_status",
    "created_at",
]

FIRST_NAMES = [
    "Aarav",
    "Aisha",
    "Alex",
    "Ananya",
    "Daniel",
    "Emma",
    "Fatima",
    "James",
    "Maya",
    "Noah",
    "Priya",
    "Rohan",
    "Sophia",
    "Vikram",
    "Zara",
]
LAST_NAMES = [
    "Brown",
    "Chen",
    "Garcia",
    "Iyer",
    "Johnson",
    "Khan",
    "Kim",
    "Mehta",
    "Patel",
    "Rao",
    "Shah",
    "Singh",
    "Smith",
    "Williams",
]
STREETS = ["Main", "Park", "Lake", "Hill", "Oak", "Maple", "Cedar", "Market", "River", "Church"]
CITIES = [
    ("Bangalore", "Karnataka", "India"),
    ("Chennai", "Tamil Nadu", "India"),
    ("Hyderabad", "Telangana", "India"),
    ("Mumbai", "Maharashtra", "India"),
    ("New York", "New York", "USA"),
    ("San Francisco", "California", "USA"),
    ("Austin", "Texas", "USA"),
    ("London", "England", "UK"),
]
EMAIL_DOMAINS = ["example.com", "mail.com", "finmail.com", "customer.net"]
STATUSES = ["Active", "Inactive"]


def parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def random_date(rng: random.Random, start: datetime, end: datetime) -> datetime:
    seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randint(0, max(seconds, 0)))


def phone_number(rng: random.Random) -> str:
    return str(rng.randint(6_000_000_000, 9_999_999_999))


def address(rng: random.Random) -> tuple[str, str, str, str]:
    city, state, country = rng.choice(CITIES)
    return f"{rng.randint(100, 9999)} {rng.choice(STREETS)} Street", city, state, country


def email_for(first: str, last: str, customer_number: int, rng: random.Random) -> str:
    return f"{first}.{last}.{customer_number}@{rng.choice(EMAIL_DOMAINS)}".lower()


def make_customer(customer_number: int, rng: random.Random, start: datetime, end: datetime) -> dict[str, str]:
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    street, city, state, country = address(rng)
    created_at = random_date(rng, start, end - timedelta(days=60))

    return {
        "customer_id": f"C{customer_number:06d}",
        "customer_name": f"{first} {last}",
        "email": email_for(first, last, customer_number, rng),
        "phone": phone_number(rng),
        "address": street,
        "city": city,
        "state": state,
        "country": country,
        "customer_status": rng.choices(STATUSES, weights=[92, 8], k=1)[0],
        "created_at": created_at.isoformat(),
    }


def changed_customer(row: dict[str, str], rng: random.Random, end: datetime) -> dict[str, str]:
    changed = dict(row)
    change_date = parse_date(row["created_at"]) + timedelta(days=rng.randint(15, 180))
    change_date = min(change_date, end)

    for field in rng.sample(["address", "email", "phone", "customer_status"], k=rng.randint(1, 3)):
        if field == "address":
            changed["address"], changed["city"], changed["state"], changed["country"] = address(rng)
        elif field == "email":
            first, last = changed["customer_name"].split(" ", 1)
            changed["email"] = email_for(first, last, rng.randint(10_000, 99_999), rng)
        elif field == "phone":
            changed["phone"] = phone_number(rng)
        else:
            changed["customer_status"] = "Inactive" if row["customer_status"] == "Active" else "Active"

    changed["created_at"] = change_date.isoformat()
    return changed


def generate_customers(count: int, change_rate: float, seed: int, start: datetime, end: datetime) -> list[dict[str, str]]:
    if count < 1:
        raise ValueError("count must be at least 1")
    if not 0 <= change_rate <= 1:
        raise ValueError("change-rate must be between 0 and 1")
    if start >= end:
        raise ValueError("start-date must be before end-date")

    rng = random.Random(seed)
    customers = [make_customer(i, rng, start, end) for i in range(1, count + 1)]
    change_count = int(round(count * change_rate))
    changed_ids = rng.sample(range(count), k=min(change_count, count))
    rows = customers + [changed_customer(customers[i], rng, end) for i in changed_ids]
    return sorted(rows, key=lambda row: (row["created_at"], row["customer_id"]))


def write_csv(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def self_check() -> None:
    rows = generate_customers(
        count=20,
        change_rate=0.25,
        seed=7,
        start=parse_date("2025-01-01"),
        end=parse_date("2026-01-01"),
    )
    assert set(rows[0]) == set(FIELDS)
    assert len(rows) == 25
    assert len({row["customer_id"] for row in rows}) == 20
    assert any(sum(row["customer_id"] == other["customer_id"] for other in rows) > 1 for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate realistic customer CSV snapshots.")
    parser.add_argument("--count", type=int, default=500, help="Number of unique customers to generate.")
    parser.add_argument("--change-rate", type=float, default=0.2, help="Share of customers with a later changed row.")
    parser.add_argument("--seed", type=int, default=42, help="Seed for repeatable output.")
    parser.add_argument("--start-date", default="2025-01-01", help="Inclusive ISO start date.")
    parser.add_argument("--end-date", default="2026-01-01", help="Inclusive ISO end date.")
    parser.add_argument("--output", default="data/customers/customers.csv", help="Output CSV path.")
    parser.add_argument("--self-check", action="store_true", help="Run generator assertions and exit.")
    args = parser.parse_args()

    if args.self_check:
        self_check()
        return

    rows = generate_customers(
        count=args.count,
        change_rate=args.change_rate,
        seed=args.seed,
        start=parse_date(args.start_date),
        end=parse_date(args.end_date),
    )
    write_csv(rows, Path(args.output))
    print(f"Wrote {len(rows)} customer rows to {args.output}")


if __name__ == "__main__":
    main()
