import os

from fastapi import FastAPI, Header, HTTPException
from google.auth.transport import requests
from google.oauth2 import id_token

app = FastAPI(title="House Pricing Web BFF")

GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me")
def me(authorization: str | None = Header(default=None)) -> dict:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header",
        )

    token = authorization.removeprefix("Bearer ").strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing ID token",
        )

    try:
        claims = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid Google ID token",
        )

    return {
        "authenticated": True,
        "user": {
            "id": claims["sub"],
            "email": claims.get("email"),
            "name": claims.get("name"),
            "picture": claims.get("picture"),
        },
    }
