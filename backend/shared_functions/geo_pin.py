"""Map pin + client file metadata helpers (CB-06 / CB-08)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def _parse_location_blob(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("{"):
            try:
                parsed = json.loads(text)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {"label": text}
        return {"label": text}
    return {}


def merge_grievance_location_blob(
    existing: Any,
    patch: Dict[str, Any],
) -> str:
    """Merge structured location/metadata into grievance_location JSON text."""
    base = _parse_location_blob(existing)
    for key, value in patch.items():
        if value is None:
            continue
        if key == "files" and isinstance(value, list):
            files = base.get("files")
            if not isinstance(files, list):
                files = []
            files.extend(value)
            base["files"] = files
        elif isinstance(value, dict) and isinstance(base.get(key), dict):
            merged = dict(base[key])
            merged.update(value)
            base[key] = merged
        else:
            base[key] = value
    return json.dumps(base, ensure_ascii=False)


def build_pin_patch(lat: float, lng: float, location_code: Optional[str] = None) -> Dict[str, Any]:
    pin: Dict[str, Any] = {"lat": lat, "lng": lng}
    if location_code:
        pin["location_code"] = location_code
    return {"pin": pin, "source": "map_pin"}


def build_file_exif_patch(file_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    entry = {"file_id": file_id}
    for key in ("captured_at", "lat", "lng", "altitude"):
        if metadata.get(key) is not None:
            entry[key] = metadata[key]
    return {"files": [entry]}
