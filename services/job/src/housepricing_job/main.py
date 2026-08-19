import os


def main() -> None:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    bucket_name = os.environ.get("GCS_BUCKET")

    print(f"Project: {project_id}")
    print(f"Bucket: {bucket_name}")


if __name__ == "__main__":
    main()