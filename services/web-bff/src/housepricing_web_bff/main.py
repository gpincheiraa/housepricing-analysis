import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from urllib.parse import urlencode

import requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.auth.transport import requests as google_requests
from google.cloud import secretmanager
from google.oauth2 import id_token

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
GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]

ML_AUTH_URL = "https://auth.mercadolibre.cl/authorization"
ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

ML_REDIRECT_URI = (
    "https://housepricing-web-bff-vyghkhukra-tl.a.run.app"
    "/oauth/mercadolibre/callback"
)

OAUTH_STATE_SECRET = "ml-oauth-state-secret"
OAUTH_STATE_TTL = 600


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


def generate_code_verifier() -> str:
    return secrets.token_urlsafe(64)


def generate_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(
        code_verifier.encode("ascii")
    ).digest()

    return base64.urlsafe_b64encode(
        digest
    ).rstrip(b"=").decode("ascii")


def create_state(
    google_user_id: str,
    code_verifier: str,
) -> str:
    payload = {
        "google_user": google_user_id,
        "code_verifier": code_verifier,
        "expires_at": int(time.time()) + OAUTH_STATE_TTL,
        "nonce": secrets.token_urlsafe(16),
    }

    payload_bytes = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode("utf-8")

    payload_encoded = base64.urlsafe_b64encode(
        payload_bytes
    ).rstrip(b"=").decode("ascii")

    secret = get_secret(OAUTH_STATE_SECRET).encode("utf-8")

    signature = hmac.new(
        secret,
        payload_encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()

    signature_encoded = base64.urlsafe_b64encode(
        signature
    ).rstrip(b"=").decode("ascii")

    return f"{payload_encoded}.{signature_encoded}"


def validate_state(state: str) -> dict:
    try:
        payload_encoded, signature_encoded = state.split(".", 1)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state",
        )

    secret = get_secret(OAUTH_STATE_SECRET).encode("utf-8")

    expected_signature = hmac.new(
        secret,
        payload_encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()

    try:
        received_signature = base64.urlsafe_b64decode(
            signature_encoded + "=" * (
                -len(signature_encoded) % 4
            )
        )
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state",
        )

    if not hmac.compare_digest(
        received_signature,
        expected_signature,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state",
        )

    try:
        payload_bytes = base64.urlsafe_b64decode(
            payload_encoded + "=" * (
                -len(payload_encoded) % 4
            )
        )

        payload = json.loads(
            payload_bytes.decode("utf-8")
        )
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state",
        )

    if payload.get("expires_at", 0) < int(time.time()):
        raise HTTPException(
            status_code=400,
            detail="Expired OAuth state",
        )

    if not payload.get("google_user"):
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state",
        )

    if not payload.get("code_verifier"):
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state",
        )

    return payload


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


@app.get("/oauth/mercadolibre")
def mercadolibre_authorize(
    authorization: str | None = Header(default=None),
) -> dict:
    claims = get_google_user(authorization)

    google_user_id = claims["sub"]

    client_id, _ = get_ml_credentials()

    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(
        code_verifier
    )

    state = create_state(
        google_user_id,
        code_verifier,
    )

    authorization_url = (
        f"{ML_AUTH_URL}?"
        + urlencode(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": ML_REDIRECT_URI,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
    )

    return {
        "authorization_url": authorization_url,
    }


@app.get("/oauth/mercadolibre/callback")
def mercadolibre_callback(
    code: str,
    state: str,
):
    state_data = validate_state(state)

    code_verifier = state_data["code_verifier"]

    client_id, client_secret = get_ml_credentials()

    response = requests.post(
        ML_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": ML_REDIRECT_URI,
            "code_verifier": code_verifier,
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
