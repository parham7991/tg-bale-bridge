"""شیم سازگاری — منطق بله به پکیج ``bridge/bale`` منتقل شد.

    from bridge.bale_user import BaleUserAPI   # هنوز کار می‌کند
    from bridge.bale import BaleUserAPI        # شکل جدید (ترجیحی)
"""
from .bale import (  # noqa: F401
    BaleBotGateway,
    BaleEventRouter,
    BaleSession,
    BaleUserAPI,
    _classify_document,
    classify_document,
    extract_id,
    extract_user,
    unwrap,
)

__all__ = [
    "BaleUserAPI", "BaleBotGateway", "BaleEventRouter", "BaleSession",
    "classify_document", "_classify_document", "extract_id", "extract_user", "unwrap",
]
