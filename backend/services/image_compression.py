"""Server-side image normalization for chatbot complainant uploads (libvips + pyvips)."""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Optional

from backend.config.constants import (
    IMAGE_COMPRESS_JPEG_QUALITY,
    IMAGE_COMPRESS_MAX_LONG_EDGE,
    IMAGE_COMPRESS_SKIP_MAX_BYTES,
    IMAGE_COMPRESS_SKIP_MAX_LONG_EDGE,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImageCompressPolicy:
    max_long_edge: int = IMAGE_COMPRESS_MAX_LONG_EDGE
    jpeg_quality: int = IMAGE_COMPRESS_JPEG_QUALITY
    skip_max_long_edge: int = IMAGE_COMPRESS_SKIP_MAX_LONG_EDGE
    skip_max_bytes: int = IMAGE_COMPRESS_SKIP_MAX_BYTES


@dataclass
class CompressResult:
    original_bytes: int
    compressed_bytes: int
    width: Optional[int]
    height: Optional[int]
    status: str  # compressed | skipped | failed
    output_path: str


def get_default_policy() -> ImageCompressPolicy:
    return ImageCompressPolicy()


def _long_edge(width: int, height: int) -> int:
    return max(width, height)


def _jpeg_output_path(file_path: str) -> str:
    base, _ = os.path.splitext(file_path)
    return f"{base}.jpg"


def _probe_image(file_path: str) -> tuple[int, int]:
    import pyvips

    # libvips 8.15+ removed VipsAccess.HEADER; sequential reads dimensions from header only.
    image = pyvips.Image.new_from_file(file_path, access=pyvips.Access.SEQUENTIAL)
    return image.width, image.height


def compress_image(
    file_path: str,
    policy: Optional[ImageCompressPolicy] = None,
) -> CompressResult:
    """
    Normalize complainant images to JPEG (max long edge, quality 80, EXIF stripped).

    On failure or skip threshold match, keeps the original file and returns
    status ``skipped`` or ``failed`` without raising.
    """
    policy = policy or get_default_policy()
    original_bytes = os.path.getsize(file_path)
    width: Optional[int] = None
    height: Optional[int] = None

    try:
        import pyvips

        width, height = _probe_image(file_path)
        edge = _long_edge(width, height)

        if edge <= policy.skip_max_long_edge and original_bytes < policy.skip_max_bytes:
            logger.info(
                "image_compression skipped file=%s bytes=%s edge=%s",
                file_path,
                original_bytes,
                edge,
            )
            return CompressResult(
                original_bytes=original_bytes,
                compressed_bytes=original_bytes,
                width=width,
                height=height,
                status="skipped",
                output_path=file_path,
            )

        # Animated GIF: thumbnail uses first frame only (spec §6.3).
        thumbnail = pyvips.Image.thumbnail(
            file_path,
            policy.max_long_edge,
            size=pyvips.Size.DOWN,
        )

        output_path = _jpeg_output_path(file_path)
        fd, temp_path = tempfile.mkstemp(suffix=".jpg", dir=os.path.dirname(file_path) or ".")
        os.close(fd)

        try:
            thumbnail.jpegsave(
                temp_path,
                Q=policy.jpeg_quality,
                strip=True,
            )
            os.replace(temp_path, output_path)
            temp_path = ""

            if output_path != file_path and os.path.exists(file_path):
                os.remove(file_path)

            compressed_bytes = os.path.getsize(output_path)
            logger.info(
                "image_compression compressed file=%s original=%s compressed=%s %sx%s",
                output_path,
                original_bytes,
                compressed_bytes,
                thumbnail.width,
                thumbnail.height,
            )
            return CompressResult(
                original_bytes=original_bytes,
                compressed_bytes=compressed_bytes,
                width=thumbnail.width,
                height=thumbnail.height,
                status="compressed",
                output_path=output_path,
            )
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as exc:
        logger.warning(
            "image_compression failed file=%s error=%s — keeping original",
            file_path,
            exc,
            exc_info=True,
        )
        return CompressResult(
            original_bytes=original_bytes,
            compressed_bytes=original_bytes,
            width=width,
            height=height,
            status="failed",
            output_path=file_path,
        )


def log_heif_availability() -> None:
    """Log whether HEIF loaders are available (call from Celery worker startup)."""
    try:
        import pyvips

        heif_suffixes = [s for s in pyvips.get_suffixes() if "heif" in s.lower()]
        logger.info("pyvips HEIF suffixes: %s", heif_suffixes or "none")
    except Exception as exc:
        logger.warning("pyvips HEIF probe failed: %s", exc)
