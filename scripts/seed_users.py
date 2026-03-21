"""Seed the database with sample users and policies."""

import asyncio
from backend.app.db.session import init_db, async_session
from backend.app.db import crud


SAMPLE_USERS = [
    ("alice", "Alice Chen"),
    ("bob", "Bob Martinez"),
    ("charlie", "Charlie Kim"),
]

SAMPLE_POLICIES = [
    ("approve_transfer", "critical"),
    ("delete_user", "critical"),
    ("export_data", "high"),
    ("view_report", "low"),
]


async def main():
    await init_db()
    async with async_session() as db:
        for user_id, display_name in SAMPLE_USERS:
            existing = await crud.get_user(db, user_id)
            if not existing:
                await crud.create_user(db, user_id, display_name)
                print(f"Created user: {user_id}")
            else:
                print(f"User already exists: {user_id}")

        for action, risk_level in SAMPLE_POLICIES:
            await crud.upsert_policy(db, action, risk_level)
            print(f"Policy set: {action} -> {risk_level}")


if __name__ == "__main__":
    asyncio.run(main())
