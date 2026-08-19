import os
import secrets
from urllib.parse import urlencode

import requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from google.cloud import secretmanager

app = FastAPI(title="House Pricing Web BFF")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://gpincheiraa.github.io",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Authorization"],
)

GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]

ML_REDIRECT_URI = (
    "https://housepricing-web-bff-vyghkhukra-tl.a.run.app"
    "/oauth/mercadolibre/callback"
)

ML_AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]

def get_secret(secret_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()

    name = (
        f"projects/{GCP_PROJECT_ID}"
        f"/secrets/{secret_id}/versions/latest"
    )

    response = client.access_secret_version(
        request={"name": name}
    )

    return response.payload.data.decode("utf-8")

def get_ml_credentials() -> tuple[str, str]:
    client_id = get_secret("ml-client-id")
    client_secret = get_secret("ml-client-secret")

    return client_id, client_secret

def get_google_user(
    authorization: str | None,
) -> dict:
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
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid Google ID token",
        )

    return claims


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me")
def me(
    authorization: str | None = Header(default=None),
) -> dict:
    claims = get_google_user(authorization)

    return {
        "authenticated": True,
        "user": {
            "id": claims["sub"],
            "email": claims.get("email"),
            "name": claims.get("name"),
            "picture": claims.get("picture"),
        },
    }

@app.get("/oauth/mercadolibre/callback")
def mercadolibre_callback(
    code: str,
    state: str,
):
    client_id, client_secret = get_ml_credentials()

    response = requests.post(
        ML_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": ML_REDIRECT_URI,
        },
        timeout=15,
    )

    if not response.ok:
        raise HTTPException(
            status_code=502,
            detail="Mercado Libre token exchange failed",
        )

    tokens = response.json()

    return {
        "status": "authorized",
        "ml_user_id": tokens.get("user_id"),
        "expires_in": tokens.get("expires_in"),
    }
