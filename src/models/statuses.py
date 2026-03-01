"""Canonical purchase statuses and lifecycle transitions."""

from __future__ import annotations


class ZakupkaStatus:
    RAW = "raw"
    AI_READY = "ai_ready"
    AI_ERROR = "ai_error"
    URL_READY = "url_ready"
    STAGE4_DONE = "stage4_done"
    STAGE4_ERROR = "stage4_error"

    # Legacy statuses still present in old data snapshots.
    LISTINGS_FRESH = "listings_fresh"
    LISTINGS_STALE = "listings_stale"

    # UI-only statuses (do not participate in backend lifecycle).
    AI_PROCESSING = "ai_processing"
    USER_SELECTED = "user_selected"


STAGE2_PENDING_STATUSES = (
    ZakupkaStatus.RAW,
    ZakupkaStatus.AI_ERROR,
)

STAGE4_QUEUE_STATUSES = (
    ZakupkaStatus.URL_READY,
    ZakupkaStatus.STAGE4_ERROR,
)

STAGE4_PROCESSED_STATUSES = (
    ZakupkaStatus.STAGE4_DONE,
    ZakupkaStatus.LISTINGS_FRESH,
    ZakupkaStatus.LISTINGS_STALE,
)

PIPELINE_LIFECYCLE_TRANSITIONS = {
    ZakupkaStatus.RAW: (
        ZakupkaStatus.AI_READY,
        ZakupkaStatus.AI_ERROR,
    ),
    ZakupkaStatus.AI_ERROR: (
        ZakupkaStatus.AI_READY,
    ),
    ZakupkaStatus.AI_READY: (
        ZakupkaStatus.URL_READY,
    ),
    ZakupkaStatus.URL_READY: (
        ZakupkaStatus.STAGE4_DONE,
        ZakupkaStatus.STAGE4_ERROR,
    ),
    ZakupkaStatus.STAGE4_ERROR: (
        ZakupkaStatus.STAGE4_DONE,
        ZakupkaStatus.STAGE4_ERROR,
    ),
}
