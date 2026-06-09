#!/usr/bin/env python3
"""Generate sample images for compression tests (no PII). Run after pyvips is installed."""

from pathlib import Path

import pyvips

FIXTURES_DIR = Path(__file__).resolve().parent


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    large = pyvips.Image.gaussnoise(2400, 1800, mean=128, sigma=30)
    large.jpegsave(str(FIXTURES_DIR / "large_phone_photo.jpg"), Q=95)

    small = pyvips.Image.black(400, 300)
    small.pngsave(str(FIXTURES_DIR / "small_screenshot.png"), compression=9)

    print(f"Wrote fixtures to {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
