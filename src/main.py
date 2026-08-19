import logging
import os

from google.cloud import storage


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting house pricing analysis job")

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    bucket_name = os.getenv("BUCKET_NAME")

    if not project_id:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is not configured")

    if not bucket_name:
        raise RuntimeError("BUCKET_NAME is not configured")

    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)

    logger.info("Connected to GCS bucket: %s", bucket.name)

    # TODO:
    # 1. Obtain Mercado Libre access token
    # 2. Query property listings
    # 3. Normalize results
    # 4. Persist raw data
    # 5. Persist normalized data

    logger.info("Job completed successfully")


if __name__ == "__main__":
    main()