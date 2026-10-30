"""
Storage & Cloudflare R2 Infrastructure Service for HocNhanhTN.
"""

from services.r2_service import (
    delete_image_from_r2,
    delete_images_from_r2,
    extract_image_keys_from_data,
    get_r2_client,
    get_stored_image,
    is_r2_configured,
    list_r2_objects,
    upload_image_to_r2,
)
from services.storage_service import storage_service

__all__ = [
    "storage_service",
    "upload_image_to_r2",
    "get_stored_image",
    "delete_image_from_r2",
    "delete_images_from_r2",
    "get_r2_client",
    "list_r2_objects",
    "extract_image_keys_from_data",
    "is_r2_configured",
]
