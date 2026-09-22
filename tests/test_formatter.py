"""تست‌های تبدیل متن/موجودیت‌ها بین تلگرام و بله."""
from telethon import types as tg_t

from bridge import formatter as fmt


class TestTgToBale:
    def test_bold_link(self):
        text = "سلام دنیا لینک"
        ents = [tg_t.MessageEntityBold(offset=5, length=4),
                tg_t.MessageEntityTextUrl(offset=10, length=4, url="https://x.ir")]
        out = fmt.tg_text_to_bale(text, ents)
        assert out == "سلام *دنیا* [لینک](https://x.ir)"

    def test_italic(self):
        ents = [tg_t.MessageEntityItalic(offset=0, length=4)]
        assert fmt.tg_text_to_bale("سلام دنیا", ents) == "_سلام_ دنیا"

    def test_utf16_offsets_with_emoji(self):
        text = "👋 سلام"  # اموجی = ۲ واحد UTF-16
        ents = [tg_t.MessageEntityBold(offset=3, length=4)]
        assert fmt.tg_text_to_bale(text, ents) == "👋 *سلام*"

    def test_no_entities_passthrough(self):
        assert fmt.tg_text_to_bale("متن ساده", None) == "متن ساده"

    def test_url_entity(self):
        text = "https://example.com"
        ents = [tg_t.MessageEntityUrl(offset=0, length=18)]
        assert "https://example.com" in fmt.tg_text_to_bale(text, ents)

    def test_unsupported_entity_stays_plain(self):
        ents = [tg_t.MessageEntityCode(offset=0, length=4)]
        assert fmt.tg_text_to_bale("کد x", ents) == "کد x"


class TestBaleToTg:
    def test_parse_all(self):
        plain, ents = fmt.bale_text_to_tg("*مهم* خبر [سایت](https://s.ir) و _کج_")
        assert plain == "مهم خبر سایت و کج"
        assert ("bold", 0, 3, None) in ents
        assert ("text_link", 8, 4, "https://s.ir") in ents
        assert ("italic", 15, 2, None) in ents

    def test_plain(self):
        assert fmt.bale_text_to_tg("بدون فرمت") == ("بدون فرمت", [])

    def test_empty(self):
        assert fmt.bale_text_to_tg("") == ("", [])


class TestUtilities:
    def test_truncate(self):
        assert fmt.truncate("abcdef", 4) == "abc…"
        assert fmt.truncate("abc", 4) == "abc"

    def test_split_text(self):
        parts = fmt.split_text("الف" * 50, 100)
        assert len(parts) == 2
        assert "".join(parts) == "الف" * 50
        assert all(len(p) <= 100 for p in parts)

    def test_split_by_lines(self):
        text = "\n".join(["x" * 30] * 5)
        parts = fmt.split_text(text, 65)
        assert len(parts) > 1
        assert "".join(p for p in parts) == text

    def test_join_header(self):
        assert fmt.join_header("هدر", "بدنه") == "هدر\nبدنه"
        assert fmt.join_header("هدر", "") == "هدر"
        assert fmt.join_header("", "بدنه") == "بدنه"


class TestRenderers:
    def test_poll(self):
        poll = tg_t.MessageMediaPoll(
            poll=tg_t.Poll(
                id=1, question=tg_t.TextWithEntities(text="غذا؟", entities=[]),
                answers=[
                    tg_t.PollAnswer(
                        text=tg_t.TextWithEntities(text="پیتزا", entities=[]), option=b"0"),
                    tg_t.PollAnswer(
                        text=tg_t.TextWithEntities(text="قورمه", entities=[]), option=b"1"),
                ],
                closed=False, multiple_choice=False, quiz=False, public_voters=True, hash=0,
            ),
            results=None,
        )

        class M:
            media = poll

        out = fmt.render_tg_poll(M())
        assert "نظرسنجی" in out and "پیتزا" in out and "قورمه" in out

    def test_bale_forward_header(self):
        assert "منبع" in fmt.bale_forward_header(
            {"forward_from_chat": {"id": 1, "title": "منبع"}})
        assert "علی" in fmt.bale_forward_header(
            {"forward_from": {"id": 1, "first_name": "علی"}})
        assert fmt.bale_forward_header({}) == ""
