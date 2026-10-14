from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv(override=False)
_client: MongoClient | None = None

def get_client():
    global _client
    if _client is None:
        _client = MongoClient(os.getenv("MONGO_URI"), tz_aware=True)
    return _client

def get_db():
    client = get_client()
    return client[os.getenv("MONGO_DB")]

def ping_db():
    try:
        client = get_client()
        res = client.admin.command("ping")
        return bool(res.get("ok"))
    except Exception:
        return False

def close_client():
    global _client
    if _client is not None:
        _client.close()
        _client = None
