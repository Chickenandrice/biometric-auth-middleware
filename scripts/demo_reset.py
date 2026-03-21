"""Reset the database and vector store for a clean demo."""

import asyncio
import os
import shutil

from backend.app.config import settings
from backend.app.db.session import init_db


async def main():
    # Remove SQLite database file
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed database: {db_path}")

    # Remove ChromaDB data
    if os.path.exists(settings.chroma_persist_dir):
        shutil.rmtree(settings.chroma_persist_dir)
        print(f"Removed vector store: {settings.chroma_persist_dir}")

    # Recreate empty database
    await init_db()
    print("Recreated empty database")
    print("Demo reset complete.")


if __name__ == "__main__":
    asyncio.run(main())
