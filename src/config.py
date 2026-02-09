import os

DATABASE_URL = os.environ.get("DATABASE_URL")
OBUMA_API_KEY = os.environ.get("OBUMA_API_KEY", "")
OBUMA_BASE_URL = os.environ.get("OBUMA_BASE_URL", "https://api.obuma.cl/v1.0")
TZ = os.environ.get("TZ", "America/Santiago")
