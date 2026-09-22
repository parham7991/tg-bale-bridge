"""تست‌های بستهٔ قالب‌بندی (bridge/textfmt) — موتورهای تبدیل و رندر."""
from __future__ import annotations

from types import SimpleNamespace

from telethon import types as tg_t

from bridge.textfmt import (
    LIMIT_TEXT,
    BaleToTgEngine,
    HeadersEngine,
    RenderersEngine,
    TgToBaleEngine,
    bale_forward_header,
    join_header,
    render_tg_dice,
    render_tg_poll,
    render_tg_service,
    render_tg_venue,
    render_unsupported_bale,
    render_unsupported_tg,
    split_text,
    tg_forward_header,
    truncate,
    utf16_index_map,
    utf16_len,
)
from tests.conftest import run

# ───────────────────────────── types_map ─────────────────────────────

def test_utf16_math():
    assert utf16_len("abc") == 3
    assert utf16_len("🙂") == 2            # خارج BMP
    assert utf16_len("سلام") == 4          # داخل BMP
    m = utf16_index_map("🙂اب")
    assert m[0] == 0 and m[2] == 1 and m[3] == 2 and m[4] == 3


# ───────────────────────────── SplitEngine ─────────────────────────────

def test_truncate_and_split():
    assert truncate("abcdef", 4) == "abc…"
    assert truncate(None, 4) == ""
    parts = split_text("a" * 30, 10)
    assert all(len(p) <= 10 for p in parts) and "".join(parts) == "a" * 30
    assert split_text("", 10) == [""]


def test_split_long_single_line():
    parts = split_text("x" * 25, 10)
    assert parts == ["x" * 10, "x" * 10, "x" * 5]


# ───────────────────────────── TgToBaleEngine ─────────────────────────────

def test_engine_bold_and_nested_priority():
    ents = [tg_t.MessageEntityBold(offset=0, length=4),
            tg_t.MessageEntityItalic(offset=1, length=2)]   # همپوشان → بیرونی برنده
    out = TgToBaleEngine.convert("سلام دنیا", ents)
    assert out == "*سلام* دنیا"


def test_engine_url_variants():
    plain_link = TgToBaleEngine.convert(
        "https://s.ir", [tg_t.MessageEntityUrl(offset=0, length=11)])
    assert plain_link == "https://s.ir"                     # خودش لینک است
    titled = TgToBaleEngine.convert(
        "سایت", [tg_t.MessageEntityTextUrl(offset=0, length=4, url="https://s.ir")])
    assert titled == "[سایت](https://s.ir)"
    broken = TgToBaleEngine.convert(
        "سایت", [tg_t.MessageEntityTextUrl(offset=0, length=4, url=None)])
    assert broken == "سایت"


def test_engine_out_of_range_offsets_ignored():
    out = TgToBaleEngine.convert("کوتاه", [tg_t.MessageEntityBold(offset=50, length=5)])
    assert out == "کوتاه"


# ───────────────────────────── BaleToTgEngine ─────────────────────────────

def test_engine_parse_all_with_offsets():
    plain, ents = BaleToTgEngine.convert("*مهم* خبر [سایت](https://s.ir) و _کج_")
    assert plain == "مهم خبر سایت و کج"
    assert ("bold", 0, 3, None) in ents
    assert ("text_link", 8, 4, "https://s.ir") in ents
    assert ("italic", 15, 2, None) in ents


def test_engine_roundtrip_tg_bale_tg():
    ents = [tg_t.MessageEntityBold(offset=0, length=3)]
    md = TgToBaleEngine.convert("مهم!", ents)
    plain, back = BaleToTgEngine.convert(md)
    assert plain == "مهم!" and back[0][:3] == ("bold", 0, 3)


# ───────────────────────────── HeadersEngine ─────────────────────────────

def test_headers_bale_variants():
    assert "منبع" in bale_forward_header({"forward_from_chat": {"id": 1, "title": "منبع"}})
    assert "@chan" in bale_forward_header(
        {"forward_from_chat": {"id": 1, "username": "chan"}})
    assert "علی" in bale_forward_header(
        {"forward_from": {"id": 1, "first_name": "علی", "last_name": "رضایی"}})
    assert bale_forward_header({}) == ""


def test_headers_tg_with_client_lookup():
    class Fwd:
        from_name = None
        from_id = SimpleNamespace()
        post_author = None

    class Msg:
        forward = Fwd()

    class Client:
        async def get_entity(self, ref):
            return SimpleNamespace(title="کانال منبع", first_name=None, last_name=None)

    out = run(tg_forward_header(Msg(), Client()))
    assert "کانال منبع" in out


def test_headers_tg_no_forward():
    class Msg:
        forward = None

    assert run(tg_forward_header(Msg(), None)) == ""


# ───────────────────────────── RenderersEngine ─────────────────────────────

def _poll_msg():
    poll = tg_t.MessageMediaPoll(
        poll=tg_t.Poll(
            id=1, question=tg_t.TextWithEntities(text="غذا؟", entities=[]),
            answers=[
                tg_t.PollAnswer(text=tg_t.TextWithEntities(text="پیتزا", entities=[]),
                                option=b"0"),
                tg_t.PollAnswer(text=tg_t.TextWithEntities(text="قورمه", entities=[]),
                                option=b"1"),
            ],
            closed=False, multiple_choice=True, quiz=False, public_voters=True, hash=0,
        ),
        results=None,
    )
    return SimpleNamespace(media=poll)


def test_renderers_poll_and_multiple_choice():
    out = render_tg_poll(_poll_msg())
    assert "غذا؟" in out and "پیتزا" in out and "قورمه" in out
    assert "چند گزینه‌ای" in out


def test_renderers_all_with_broken_msg():
    broken = SimpleNamespace(media=None, message=None, action=None)
    assert "🎲" in render_tg_dice(broken)
    assert "📍" in render_tg_venue(broken)
    assert "سرویس" in render_tg_service(broken)
    assert "پشتیبانی‌نشده" in render_unsupported_tg(broken)
    assert "پشتیبانی‌نشده" in render_unsupported_bale({})


def test_renderers_service_and_unsupported_text():
    class Act:
        pass
    msg = SimpleNamespace(action=Act(), message=None, media=None)
    assert "Act" in render_tg_service(msg)
    msg2 = SimpleNamespace(action=None, message="  متن خودم  ", media=None)
    assert render_unsupported_tg(msg2) == "متن خودم"
    assert render_unsupported_bale({"caption": "کپشن"}) == "کپشن"


def test_renderers_dice_and_venue_ok():
    dice = SimpleNamespace(media=SimpleNamespace(emoticon="🏀", value=3),
                           message=None, action=None)
    assert "🏀" in render_tg_dice(dice) and "3" in render_tg_dice(dice)
    venue = SimpleNamespace(
        media=SimpleNamespace(venue=SimpleNamespace(title="کافه", address="تهران")),
        message=None, action=None)
    assert "کافه" in render_tg_venue(venue) and "تهران" in render_tg_venue(venue)


# ───────────────────────────── join_header و سازگاری ─────────────────────────────

def test_join_header_rules():
    assert join_header("هدر", "بدنه") == "هدر\nبدنه"
    assert join_header("هدر", "  ") == "هدر"
    assert join_header("", "بدنه") == "بدنه"
    assert join_header("", "") == ""


def test_limit_constant_and_engine_classes():
    assert LIMIT_TEXT == 4096
    for cls in (TgToBaleEngine, BaleToTgEngine, HeadersEngine, RenderersEngine):
        assert hasattr(cls, "convert") or hasattr(cls, "tg_forward_header") \
            or hasattr(cls, "render_tg_poll")
