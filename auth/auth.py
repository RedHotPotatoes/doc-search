import os
from datetime import timedelta

from authlib.integrations.base_client import OAuthError
from authlib.oauth2.rfc6749 import OAuth2Token
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from omegaconf import OmegaConf
from starlette import status

from auth.utils_auth import create_access_token, create_user_from_google_info, oauth
from auth.validators import GoogleUser
from core.db import AsyncMongoDB, init_mongo_db_instance

auth_db: AsyncMongoDB = init_mongo_db_instance(
    is_async=True, default_db="troubleshooting", default_collection="users"
)

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


BACKEND_URL = os.getenv("BACKEND_URL")
FRONTEND_URL = os.getenv("FRONTEND_URL")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = f"{BACKEND_URL}/auth/callback/google"

white_list_emails = OmegaConf.to_container(
    OmegaConf.load("conf/whitelist_emails.yaml")
)


@router.get("/google")
async def login_google(request: Request):
    return await oauth.google.authorize_redirect(request, GOOGLE_REDIRECT_URI)


@router.get("/callback/google")
async def auth_google(request: Request):
    try:
        user_response: OAuth2Token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    user_info = user_response.get("userinfo")
    google_user = GoogleUser(**user_info)
    if google_user.email not in white_list_emails:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized to access this resource",
        )

    existing_user = await auth_db.get(
        {"google_sub": str(google_user.sub)}, collection="users"
    )
    if existing_user is not None:
        user = existing_user
    else:
        await create_user_from_google_info(google_user, auth_db)
        user = await auth_db.get(
            {"google_sub": str(google_user.sub)}, collection="users"
        )

    access_token = create_access_token(
        user["name"], str(user["_id"]), timedelta(days=7)
    )
    return RedirectResponse(f"{FRONTEND_URL}?access_token={access_token}")
