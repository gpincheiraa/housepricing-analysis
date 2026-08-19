import base64
import json
import logging
import os
from datetime import datetime, timezone

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from google.cloud import secretmanager, storage


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
BUCKET_NAME = os.environ["GCS_BUCKET"]

ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
ML_SEARCH_URL = "https://api.mercadolibre.com/sites/MLC/search"

ML_CLIENT_ID_SECRET = "ml-client-id"
ML_CLIENT_SECRET_SECRET = "ml-client-secret"
ML_ENCRYPTION_KEY_SECRET = "ml-token-encryption-key"

# Mercado Libre Chile - categoría Inmuebles:
# https://api.mercadolibre.com/categories/MLC1459
ML_CATEGORY_ID = "MLC1459"


def get_secret(name: str) -> str:
    client = secretmanager.SecretManagerServiceClient()

    response = client.access_secret_version(
        request={
            "name": (
                f"projects/{PROJECT_ID}"
                f"/secrets/{name}/versions/latest"
            )
        }
    )

    return response.payload.data.decode()


def get_bucket():
    return storage.Client().bucket(BUCKET_NAME)


def get_ml_credentials(user_id: str) -> dict:
    blob = get_bucket().blob(
        f"users/{user_id}/mercadolibre.json.enc"
    )

    if not blob.exists():
        raise RuntimeError(
            "Mercado Libre account not connected"
        )

    document = json.loads(
        blob.download_as_text()
    )

    key = base64.b64decode(
        get_secret(ML_ENCRYPTION_KEY_SECRET)
    )

    plaintext = AESGCM(key).decrypt(
        base64.b64decode(document["nonce"]),
        base64.b64decode(document["ciphertext"]),
        user_id.encode(),
    )

    return json.loads(
        plaintext.decode()
    )


def get_access_token(user_id: str) -> str:
    credentials = get_ml_credentials(user_id)

    response = httpx.post(
        ML_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": get_secret(
                ML_CLIENT_ID_SECRET
            ),
            "client_secret": get_secret(
                ML_CLIENT_SECRET_SECRET
            ),
            "refresh_token": credentials[
                "refresh_token"
            ],
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()["access_token"]


def execute_search(
    user_id: str,
    search_config: dict,
) -> None:
    token = get_access_token(user_id)

    params = {
        "category": ML_CATEGORY_ID,
        "limit": 50,
    }

    response = httpx.get(
        ML_SEARCH_URL,
        params=params,
        headers={
            "Authorization": f"Bearer {token}",
        },
        timeout=30,
    )

    logger.info(
        "Mercado Libre search: user=%s search=%s status=%s",
        user_id,
        search_config.get("id"),
        response.status_code,
    )

    try:
        body = response.json()
    except ValueError:
        body = response.text

    executed_at = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%dT%H-%M-%S.%fZ"
    )

    search_id = search_config["id"]

    path = (
        f"users/{user_id}"
        f"/results/{search_id}"
        f"/raw/{executed_at}.json"
    )

    document = {
        "executed_at": executed_at,
        "search": search_config,
        "request": {
            "method": "GET",
            "url": str(response.url),
            "params": params,
        },
        "response": {
            "status_code": response.status_code,
            "body": body,
        },
    }

    get_bucket().blob(path).upload_from_string(
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
        ),
        content_type="application/json",
    )

    logger.info(
        "RAW result saved: gs://%s/%s",
        BUCKET_NAME,
        path,
    )


def get_user_ids() -> set[str]:
    user_ids = set()

    for blob in get_bucket().list_blobs(
        prefix="users/"
    ):
        parts = blob.name.split("/")

        if len(parts) > 1 and parts[1]:
            user_ids.add(parts[1])

    return user_ids


def process_user(user_id: str) -> None:
    blob = get_bucket().blob(
        f"users/{user_id}/settings.json"
    )

    if not blob.exists():
        return

    settings = json.loads(
        blob.download_as_text()
    )

    searches = [
        search
        for search in settings.get(
            "searches",
            [],
        )
        if search.get("enabled", True)
    ]

    for search in searches:
        try:
            execute_search(
                user_id,
                search,
            )
        except Exception:
            logger.exception(
                "Search failed: user=%s search=%s",
                user_id,
                search.get("id"),
            )


def main() -> None:
    logger.info(
        "Starting House Pricing Job"
    )

    for user_id in get_user_ids():
        process_user(user_id)

    logger.info(
        "House Pricing Job completed"
    )


if __name__ == "__main__":
    main()
