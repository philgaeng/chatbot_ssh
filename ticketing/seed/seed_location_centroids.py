"""Apply district centroid coordinates to ticketing.locations (level 2, NP)."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from ticketing.constants.nepal_district_centroids import NEPAL_DISTRICT_CENTROIDS

log = logging.getLogger(__name__)


def apply_district_centroids(bind: Any) -> int:
    """
    Set latitude/longitude on NP district rows. Idempotent.
    Returns number of rows updated.
    """
    updated = 0
    for location_code, (lat, lng) in NEPAL_DISTRICT_CENTROIDS.items():
        result = bind.execute(
            text(
                """
                UPDATE ticketing.locations
                SET latitude = :lat, longitude = :lng
                WHERE location_code = :code
                  AND country_code = 'NP'
                  AND level_number = 2
                """
            ),
            {"lat": lat, "lng": lng, "code": location_code},
        )
        updated += result.rowcount or 0
    log.info("apply_district_centroids: updated %d district rows", updated)
    return updated
