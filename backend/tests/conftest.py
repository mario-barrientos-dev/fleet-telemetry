from __future__ import annotations

import os

# Ensure imports of app.config don't crash when no .env is present.
os.environ.setdefault("APP_DATABASE_URL", "postgresql+asyncpg://fleet:fleet@localhost:5432/fleet")
os.environ.setdefault("APP_ENVIRONMENT", "test")
