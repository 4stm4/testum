"""Upload a file to MinIO backups/ prefix."""
import os
import sys
from minio import Minio

def main():
    src_path = sys.argv[1]
    object_name = f"backups/{sys.argv[2]}"

    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )
    bucket = os.environ["MINIO_BUCKET"]

    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)

    client.fput_object(bucket, object_name, src_path, content_type="application/gzip")
    print(f"Uploaded {src_path} → {bucket}/{object_name}")

if __name__ == "__main__":
    main()
