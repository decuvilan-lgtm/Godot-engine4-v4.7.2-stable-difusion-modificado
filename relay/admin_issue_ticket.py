#!/usr/bin/env python3
"""Create an account if needed and issue a one-time device enrollment ticket.

Run manually in a trusted environment with DATABASE_URL set. The ticket is
printed once; never commit it, add it to build logs, or paste it into source.
"""
import argparse, asyncio, hashlib, os, secrets
import asyncpg

def sha256(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()

async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--platform", choices=("android", "linux"), required=True)
    parser.add_argument("--ttl-minutes", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.ttl_minutes <= 1440:
        parser.error("--ttl-minutes must be between 1 and 1440")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        parser.error("DATABASE_URL must be set in the trusted environment")
    ticket = secrets.token_urlsafe(32)
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            account_id = await conn.fetchval(
                """INSERT INTO accounts(email) VALUES($1)
                   ON CONFLICT(email) DO UPDATE SET updated_at=now()
                   RETURNING id""", args.email.strip().lower())
            await conn.execute(
                """INSERT INTO enrollment_tickets(account_id, ticket_hash, intended_platform, expires_at)
                   VALUES($1,$2,$3,now() + ($4 * interval '1 minute'))""",
                account_id, sha256(ticket), args.platform, args.ttl_minutes)
    finally:
        await conn.close()
    print("Account ID:", account_id)
    print("Platform:", args.platform)
    print("Expires in minutes:", args.ttl_minutes)
    print("ONE-TIME ENROLLMENT TICKET (shown once):", ticket)

if __name__ == "__main__":
    asyncio.run(main())
