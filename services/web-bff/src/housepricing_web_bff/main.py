import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time

from urllib.parse import urlencode

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.auth.transport import requests as google_requests
from google.cloud import secretmanager
from google.cloud import storage
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

logger = logging.getLogger(__name__)
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GCS_BUCKET = os.environ["GCS_BUCKET"]

ML_AUTH_URL = "https://auth.mercadolibre.cl/authorization"
ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

ML_REDIRECT_URI = (
    "https://housepricing-web-bff-vyghkhukra-tl.a.run.app"
    "/oauth/mercadolibre/callback"
)

ML_CLIENT_ID_SECRET = "ml-client-id"
ML_CLIENT_SECRET_SECRET = "ml-client-secret"
OAUTH_STATE_SECRET = "ml-oauth-state-secret"
ML_TOKEN_ENCRYPTION_KEY_SECRET = "ml-token-encryption-key"

OAUTH_STATE_TTL = 600


# ---------------------------------------------------------------------------
# Secret Manager
# ---------------------------------------------------------------------------

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
    client_id = get_secret(ML_CLIENT_ID_SECRET)
    client_secret = get_secret(ML_CLIENT_SECRET_SECRET)

    return client_id, client_secret


def get_encryption_key() -> bytes:
    encoded_key = get_secret(
        ML_TOKEN_ENCRYPTION_KEY_SECRET
    )

    try:
        key = base64.b64decode(encoded_key)
    except Exception as exc:
        raise RuntimeError(
            "Invalid ML token encryption key"
        ) from exc

    if len(key) not in (16, 24, 32):
        raise RuntimeError(
            "ML token encryption key must be 16, 24 or 32 bytes"
        )

    return key


# ---------------------------------------------------------------------------
# Google authentication
# ---------------------------------------------------------------------------

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

    logger.info(
        "Google user authenticated: %s",
        {
            "sub": claims.get("sub"),
            "email": claims.get("email"),
            "email_verified": claims.get("email_verified"),
            "name": claims.get("name"),
            "given_name": claims.get("given_name"),
            "family_name": claims.get("family_name"),
            "picture": claims.get("picture"),
            "hd": claims.get("hd"),
        },
    )

    return claims


# ---------------------------------------------------------------------------
# PKCE
# ---------------------------------------------------------------------------

def generate_code_verifier() -> str:
    return secrets.token_urlsafe(64)


def generate_code_challenge(
    code_verifier: str,
) -> str:
    digest = hashlib.sha256(
        code_verifier.encode("ascii")
    ).digest()

    return base64.urlsafe_b64encode(
        digest
    ).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# OAuth state
# ---------------------------------------------------------------------------

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

    payload_encoded = (
        base64.urlsafe_b64encode(payload_bytes)
        .rstrip(b"=")
        .decode("ascii")
    )

    secret = get_secret(
        OAUTH_STATE_SECRET
    ).encode("utf-8")

    signature = hmac.new(
        secret,
        payload_encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()

    signature_encoded = (
        base64.urlsafe_b64encode(signature)
        .rstrip(b"=")
        .decode("ascii")
    )

    return f"{payload_encoded}.{signature_encoded}"


def validate_state(state: str) -> dict:
    try:
        payload_encoded, signature_encoded = state.split(
            ".",
            1,
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state",
        )

    secret = get_secret(
        OAUTH_STATE_SECRET
    ).encode("utf-8")

    expected_signature = hmac.new(
        secret,
        payload_encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()

    try:
        received_signature = base64.urlsafe_b64decode(
            signature_encoded
            + "=" * (-len(signature_encoded) % 4)
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
            payload_encoded
            + "=" * (-len(payload_encoded) % 4)
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


# ---------------------------------------------------------------------------
# Mercado Libre credential encryption
# ---------------------------------------------------------------------------

def encrypt_ml_credentials(
    google_user_id: str,
    ml_user_id: int,
    refresh_token: str,
) -> bytes:
    key = get_encryption_key()

    aes = AESGCM(key)

    nonce = secrets.token_bytes(12)

    payload = json.dumps(
        {
            "google_user_id": google_user_id,
            "ml_user_id": ml_user_id,
            "refresh_token": refresh_token,
        },
        separators=(",", ":"),
    ).encode("utf-8")

    ciphertext = aes.encrypt(
        nonce,
        payload,
        google_user_id.encode("utf-8"),
    )

    document = {
        "version": 1,
        "algorithm": "AES-256-GCM",
        "nonce": base64.b64encode(
            nonce
        ).decode("ascii"),
        "ciphertext": base64.b64encode(
            ciphertext
        ).decode("ascii"),
    }

    return json.dumps(
        document,
        separators=(",", ":"),
    ).encode("utf-8")


def save_ml_credentials(
    google_user_id: str,
    ml_user_id: int,
    refresh_token: str,
) -> None:
    storage_client = storage.Client()

    bucket = storage_client.bucket(
        GCS_BUCKET
    )

    object_name = (
        f"users/{google_user_id}/mercadolibre.json.enc"
    )

    encrypted_data = encrypt_ml_credentials(
        google_user_id=google_user_id,
        ml_user_id=ml_user_id,
        refresh_token=refresh_token,
    )

    blob = bucket.blob(object_name)

    blob.upload_from_string(
        encrypted_data,
        content_type="application/octet-stream",
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
    }


# ---------------------------------------------------------------------------
# Google user
# ---------------------------------------------------------------------------

@app.get("/me")
def me(
    authorization: str | None = Header(default=None),
) -> dict:
    claims = get_google_user(
        authorization
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


# ---------------------------------------------------------------------------
# Mercado Libre OAuth - authorization
# ---------------------------------------------------------------------------

@app.get("/oauth/mercadolibre")
def mercadolibre_authorize(
    authorization: str | None = Header(default=None),
) -> dict:
    claims = get_google_user(
        authorization
    )

    google_user_id = claims["sub"]

    client_id, _ = get_ml_credentials()

    code_verifier = generate_code_verifier()

    code_challenge = generate_code_challenge(
        code_verifier
    )

    state = create_state(
        google_user_id=google_user_id,
        code_verifier=code_verifier,
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


# ---------------------------------------------------------------------------
# Mercado Libre OAuth - callback
# ---------------------------------------------------------------------------

@app.get("/oauth/mercadolibre/callback")
def mercadolibre_callback(
    code: str,
    state: str,
):
    state_data = validate_state(
        state
    )

    google_user_id = state_data[
        "google_user"
    ]

    code_verifier = state_data[
        "code_verifier"
    ]

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
            detail={
                "message": "Mercado Libre token exchange failed",
                "status": response.status_code,
                "response": response.text,
            },
        )

    tokens = response.json()

    refresh_token = tokens.get(
        "refresh_token"
    )

    ml_user_id = tokens.get(
        "user_id"
    )

    if not refresh_token:
        raise HTTPException(
            status_code=502,
            detail=(
                "Mercado Libre did not return "
                "refresh token"
            ),
        )

    if not ml_user_id:
        raise HTTPException(
            status_code=502,
            detail=(
                "Mercado Libre did not return "
                "user id"
            ),
        )

    save_ml_credentials(
        google_user_id=google_user_id,
        ml_user_id=ml_user_id,
        refresh_token=refresh_token,
    )

    return {
        "status": "authorized",
        "ml_user_id": ml_user_id,
    }
