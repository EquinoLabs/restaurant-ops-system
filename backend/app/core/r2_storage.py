import logging
import uuid
from typing import Optional, Tuple
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.errors import ValidationError, InternalServerError

logger = logging.getLogger("roms.r2_storage")


def get_r2_client():
    """
    Returns lazily configured boto3 S3 client for Cloudflare R2 storage.
    """
    if not settings.R2_ACCOUNT_ID or not settings.R2_ACCESS_KEY_ID or not settings.R2_SECRET_ACCESS_KEY:
        raise InternalServerError("Cloudflare R2 storage credentials are not configured on the server.")

    endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def validate_image_file(contents: bytes, filename: str) -> Tuple[str, str]:
    """
    Validates file size and inspects actual content magic bytes.
    Returns tuple of (content_type, file_extension).
    """
    if not contents:
        raise ValidationError("Uploaded file is empty.")

    max_bytes = settings.R2_MAX_IMAGE_BYTES
    if len(contents) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise ValidationError(f"File size exceeds maximum limit of {max_mb}MB.")

    # Inspect magic bytes
    if contents.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    elif contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    elif contents.startswith(b"RIFF") and len(contents) >= 12 and contents[8:12] == b"WEBP":
        return "image/webp", ".webp"
    else:
        raise ValidationError("Unsupported file format or invalid image content. Allowed formats: JPEG, PNG, WebP.")


def upload_item_image(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    s3_client: Optional[any] = None,
) -> str:
    """
    Validates image bytes and uploads object to R2 bucket.
    Returns generated object key: outlets/{outlet_id}/items/{item_id}/{uuid}{ext}
    """
    content_type, ext = validate_image_file(file_bytes, filename)
    object_key = f"outlets/{outlet_id}/items/{item_id}/{uuid.uuid4().hex}{ext}"

    if s3_client is None:
        s3_client = get_r2_client()

    try:
        s3_client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=object_key,
            Body=file_bytes,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
        logger.info(f"Successfully uploaded R2 object key: {object_key}")
        return object_key
    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to upload image to R2 for item {item_id}: {str(e)}")
        raise InternalServerError("Failed to store image file in cloud storage.")


def delete_object(object_key: str, s3_client: Optional[any] = None) -> bool:
    """
    Safely deletes object key from R2 bucket.
    Returns True if deleted or ignored (if legacy URL/empty), False on error.
    """
    if not object_key or object_key.startswith("http://") or object_key.startswith("https://"):
        return True

    if s3_client is None:
        try:
            s3_client = get_r2_client()
        except Exception as e:
            logger.warning(f"Skipping R2 deletion due to client init error: {str(e)}")
            return False

    try:
        s3_client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=object_key)
        logger.info(f"Successfully deleted R2 object key: {object_key}")
        return True
    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to delete R2 object key '{object_key}': {str(e)}")
        return False
