"""Unit tests for server-side image compression (pyvips / libvips)."""

import os
import shutil
import tempfile

import pytest

pyvips = pytest.importorskip("pyvips")

from backend.config.constants import (
    IMAGE_COMPRESS_MAX_LONG_EDGE,
    IMAGE_COMPRESS_SKIP_MAX_BYTES,
)
from backend.services.image_compression import (
    ImageCompressPolicy,
    compress_image,
)


@pytest.fixture
def work_dir():
    path = tempfile.mkdtemp(prefix="img_compress_test_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _write_large_jpeg(path: str, width: int = 2400, height: int = 1800) -> None:
    noise = pyvips.Image.gaussnoise(width, height, mean=128, sigma=30)
    noise.jpegsave(path, Q=95)


def _write_small_png(path: str) -> None:
    img = pyvips.Image.black(400, 300)
    img.pngsave(path, compression=9)


def test_large_jpeg_compresses_to_max_edge(work_dir):
    src = os.path.join(work_dir, "large.jpg")
    _write_large_jpeg(src)
    original_bytes = os.path.getsize(src)

    result = compress_image(src)

    assert result.status == "compressed"
    assert result.compressed_bytes < original_bytes
    assert os.path.exists(result.output_path)
    out = pyvips.Image.new_from_file(result.output_path, access=pyvips.Access.SEQUENTIAL)
    assert max(out.width, out.height) <= IMAGE_COMPRESS_MAX_LONG_EDGE


def test_small_png_skipped(work_dir):
    src = os.path.join(work_dir, "small.png")
    _write_small_png(src)
    original_bytes = os.path.getsize(src)
    assert original_bytes < IMAGE_COMPRESS_SKIP_MAX_BYTES

    result = compress_image(src)

    assert result.status == "skipped"
    assert result.output_path == src
    assert result.compressed_bytes == original_bytes
    assert os.path.basename(result.output_path) == "small.png"


def test_invalid_file_keeps_original(work_dir):
    src = os.path.join(work_dir, "not_an_image.jpg")
    with open(src, "wb") as fh:
        fh.write(b"not a real image file")
    original_bytes = os.path.getsize(src)

    result = compress_image(src)

    assert result.status == "failed"
    assert result.output_path == src
    assert os.path.getsize(src) == original_bytes


def test_skip_policy_respects_custom_threshold(work_dir):
    src = os.path.join(work_dir, "medium.jpg")
    _write_large_jpeg(src, width=1000, height=800)
    policy = ImageCompressPolicy(skip_max_bytes=1)

    result = compress_image(src, policy=policy)

    assert result.status == "compressed"
