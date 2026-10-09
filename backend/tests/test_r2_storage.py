import io
import uuid
from unittest.mock import MagicMock, patch
import pytest

from app.core.config import get_public_image_url, settings
from app.core.errors import ValidationError, InternalServerError
from app.core import r2_storage
from app.modules.menus.models import MenuItem
from app.modules.staff.models import User


def test_get_public_image_url():
    # None or empty
    assert get_public_image_url(None) is None
    assert get_public_image_url("") is None
    assert get_public_image_url("   ") is None

    # Full HTTP/HTTPS URLs returned as is
    http_url = "http://example.com/images/food.jpg"
    https_url = "https://images.unsplash.com/photo-123"
    assert get_public_image_url(http_url) == http_url
    assert get_public_image_url(https_url) == https_url

    # Relative object keys prepended with base URL
    key = "outlets/out_123/items/item_456/abc.webp"
    expected = f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{key}"
    assert get_public_image_url(key) == expected


def test_validate_image_file():
    # JPEG
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    c_type, ext = r2_storage.validate_image_file(jpeg_bytes, "test.jpg")
    assert c_type == "image/jpeg"
    assert ext == ".jpg"

    # PNG
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    c_type, ext = r2_storage.validate_image_file(png_bytes, "test.png")
    assert c_type == "image/png"
    assert ext == ".png"

    # WebP
    webp_bytes = b"RIFF\x20\x00\x00\x00WEBPVP8 "
    c_type, ext = r2_storage.validate_image_file(webp_bytes, "test.webp")
    assert c_type == "image/webp"
    assert ext == ".webp"

    # Empty
    with pytest.raises(ValidationError, match="Uploaded file is empty"):
        r2_storage.validate_image_file(b"", "empty.jpg")

    # Invalid header
    with pytest.raises(ValidationError, match="Unsupported file format"):
        r2_storage.validate_image_file(b"NOT_AN_IMAGE_CONTENT", "bad.jpg")

    # Oversized
    big_bytes = b"\xff\xd8\xff" + b"0" * (settings.R2_MAX_IMAGE_BYTES + 10)
    with pytest.raises(ValidationError, match="File size exceeds maximum limit"):
        r2_storage.validate_image_file(big_bytes, "big.jpg")


def test_upload_item_image():
    mock_s3 = MagicMock()
    outlet_id = uuid.uuid4()
    item_id = uuid.uuid4()
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"

    key = r2_storage.upload_item_image(
        outlet_id=outlet_id,
        item_id=item_id,
        file_bytes=jpeg_bytes,
        filename="food.jpg",
        s3_client=mock_s3,
    )

    assert key.startswith(f"outlets/{outlet_id}/items/{item_id}/")
    assert key.endswith(".jpg")
    mock_s3.put_object.assert_called_once_with(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=jpeg_bytes,
        ContentType="image/jpeg",
        CacheControl="public, max-age=31536000, immutable",
    )


def test_delete_object():
    mock_s3 = MagicMock()

    # Legacy/http URL should not trigger S3 delete
    assert r2_storage.delete_object("https://example.com/img.jpg", s3_client=mock_s3) is True
    mock_s3.delete_object.assert_not_called()

    # R2 object key should call S3 delete
    key = "outlets/out_1/items/item_1/test.webp"
    assert r2_storage.delete_object(key, s3_client=mock_s3) is True
    mock_s3.delete_object.assert_called_once_with(Bucket=settings.R2_BUCKET_NAME, Key=key)


def test_api_upload_and_delete_item_image(client, db_session):
    # Login staff
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get an item
    item = db_session.query(MenuItem).filter(MenuItem.name == "Fried Fish").first()
    outlet_id = str(item.outlet_id)
    item_id = str(item.id)

    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"

    mock_s3 = MagicMock()
    with patch("app.core.r2_storage.get_r2_client", return_value=mock_s3):
        # Upload image
        upload_resp = client.post(
            f"/api/v1/outlets/{outlet_id}/items/{item_id}/image",
            headers=headers,
            files={"file": ("fish.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
        )
        assert upload_resp.status_code == 200
        data = upload_resp.json()
        assert data["id"] == item_id
        assert data["image_url"].startswith(settings.R2_PUBLIC_BASE_URL)
        assert f"outlets/{outlet_id}/items/{item_id}/" in data["image_url"]

        mock_s3.put_object.assert_called_once()

        # Delete image
        delete_resp = client.delete(
            f"/api/v1/outlets/{outlet_id}/items/{item_id}/image",
            headers=headers,
        )
        assert delete_resp.status_code == 200
        del_data = delete_resp.json()
        assert del_data["image_url"] is None

        mock_s3.delete_object.assert_called_once()
