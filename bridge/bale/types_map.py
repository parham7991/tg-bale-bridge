"""نگاشت‌ها و ابزارهای خالص بله — بدون وضعیت، بدون I/O."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Union

FileArg = Union[str, Path, bytes, Any]

#: مقادیر عددی ``ChatType`` داخلی بله → انواع Bot-API
CHAT_TYPE_NAMES = {
    1: "private",   # PRIVATE
    2: "group",     # GROUP
    3: "channel",   # CHANNEL
    4: "private",   # BOT
    5: "group",     # SUPER_GROUP
}


def chat_type_name(value: Any) -> str:
    try:
        v = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        v = 0
    return CHAT_TYPE_NAMES.get(v, "private")


#: مقدار کش برای «گروه‌مانندِ مبهم» — در آپدیت‌های بله، کانال هم ممکن است با نوع
#: group-like (ChatType.GROUP/SUPER_GROUP یا PeerType.GROUP) برسد؛ چنین مقدارهایی
#: هرگز مستقیم برای ارسال استفاده نمی‌شوند تا ResolverEngine با get_full_group
#: نوع قطعی (group/channel) را تعیین کند (رگرسیون v2.17.7: InvalidArgument رسانه).
AMBIGUOUS_GROUP = "group?"

GROUP_LIKE_CHAT_TYPES = {2, 5}     # ChatType: GROUP, SUPER_GROUP
GROUP_LIKE_PEER_TYPES = {2}        # PeerType: GROUP (= کانال‌ها و گروه‌ها با هم!)


def group_like_type_value(value: Any, peer_types: bool = False) -> bool:
    """آیا مقدار عددیِ نوع چت/پیر «گروه‌مانند» است؟ (کانال ممکن است مبهم برسد)"""
    try:
        v = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return v in (GROUP_LIKE_PEER_TYPES if peer_types else GROUP_LIKE_CHAT_TYPES)


def peer_type(chat_type_name_str: str) -> Any:
    from aiobale.enums import PeerType

    return PeerType.GROUP if chat_type_name_str in ("group", "channel") else PeerType.PRIVATE


def doc_name(doc: Any) -> str:
    name = getattr(doc, "name", None)
    if isinstance(name, dict):
        name = name.get("value") or name.get("name") or ""
    return str(name or "")


def classify_document(doc: Any) -> str:
    """نگاشت ``DocumentMessage`` یکپارچهٔ بله به نوع محتوای Bot-API."""
    mime = (getattr(doc, "mime_type", "") or "").lower()
    name = doc_name(doc).lower()
    ext = str(getattr(doc, "ext", "") or "").lower()
    if mime.startswith("image/"):
        if mime == "image/gif" or ext == "gif" or name.endswith(".gif"):
            return "animation"
        return "photo"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        if mime == "audio/ogg" or ext in ("ogg", "opus") or name.startswith("voice"):
            return "voice"
        return "audio"
    return "document"


# نام قدیمی برای سازگاری
_classify_document = classify_document


def unwrap(value: Any) -> Any:
    """باز کردن wrapperهای aiobale (مثل StringValue که مقدار در ``.value`` است)."""
    while value is not None and not isinstance(value, (str, int, float, bool)):
        inner = getattr(value, "value", None)
        if inner is None or inner is value:
            break
        value = inner
    return value


def extract_id(obj: Any) -> int:
    """استخراج شناسهٔ عددی از آبجکت‌های تودرتو (User/Contact/Peer/dict).

    نکته: پاسخ search_username در aiobale برای «کاربر/بات» در فیلد ``user``
    و برای «گروه/کانال» در فیلد ``group`` است — هر دو باید پوشش داده شوند.
    """
    for attr in ("id", "user_id", "chat_id"):
        v = getattr(obj, attr, None)
        if isinstance(v, int):
            return v
    for attr in ("user", "group", "contact", "peer", "data"):
        inner = getattr(obj, attr, None)
        if inner is not None and inner is not obj:
            found = extract_id(inner)
            if found:
                return found
    if isinstance(obj, dict):
        for key in ("id", "user_id", "chat_id"):
            v = obj.get(key)
            if isinstance(v, int):
                return v
        for key in ("user", "group", "contact", "peer"):
            if isinstance(obj.get(key), dict):
                found = extract_id(obj[key])
                if found:
                    return found
    return 0


def extract_user(obj: Any) -> Any:
    """از پاسخ search_username، آبجکت کاربر/ربات را بیرون می‌کشد."""
    for attr in ("user", "contact", "data", "peer"):
        v = getattr(obj, attr, None)
        if v is not None and hasattr(v, "id"):
            return v
    if hasattr(obj, "id") and (hasattr(obj, "access_hash") or hasattr(obj, "username")):
        return obj
    return None


# نام‌های قدیمی
_unwrap = unwrap
_extract_id = extract_id
_extract_user = extract_user
_doc_name = doc_name
_chat_type_name = chat_type_name
_peer_type = peer_type
