import os
from datetime import UTC, datetime, timedelta

from authlib.integrations.starlette_client import OAuth
from jose import jwt
from starlette.config import Config

from auth.validators import GoogleUser
from core.db import AsyncMongoDB
from dotenv import load_dotenv

load_dotenv()

ALGORITHM = "HS256"
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID") or None
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET") or None

if GOOGLE_CLIENT_ID is None or GOOGLE_CLIENT_SECRET is None:
    raise Exception("Missing env variables")

oauth = OAuth(
    Config(
        environ={
            "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
            "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
        }
    )
)
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def create_access_token(username: str, user_id: int, expires_delta: timedelta):
    encode = {"sub": username, "id": user_id}
    expires = datetime.now(UTC) + expires_delta
    encode.update({"exp": expires})

    return jwt.encode(encode, os.getenv("SECRET_KEY"), algorithm=ALGORITHM)


def decode_token(token):
    return jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=ALGORITHM)


async def create_user_from_google_info(google_user: GoogleUser, db: AsyncMongoDB):
    sub, email = google_user.sub, google_user.email

    if await db.get({"email": email}, collection="users"):
        data = {
            "google_sub": str(sub),
            "name": google_user.name,
            "updated_at": datetime.now(UTC),
        }
        return await db.update({"email": email}, {"$set": data}, collection="users")

    data = {
        "google_sub": str(sub),
        "email": email,
        "name": google_user.name,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    return await db.update({"email": email}, {"$set": data}, collection="users", upsert=True)
