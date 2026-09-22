"""تست‌های کلاسه‌بندی پیام، محتوای بله، کلاینت و دستورات."""
from telethon import types as tg_t

from bridge.admin import Admin
from bridge.bale_api import BaleAPI
from bridge.transfer import Bridge, _fp


class FakeMsg:
    def __init__(self, **kw):
        for k in ("media", "photo", "video", "video_note", "voice", "audio", "gif",
                  "sticker", "game", "document", "text", "message", "action"):
            setattr(self, k, kw.get(k))


class TestTgKind:
    def test_text(self):
        assert Bridge._tg_kind(FakeMsg(text="hi", message="hi")) == "text"

    def test_photo_video_voice(self):
        assert Bridge._tg_kind(FakeMsg(photo=object())) == "photo"
        assert Bridge._tg_kind(FakeMsg(video=object())) == "video"
        assert Bridge._tg_kind(FakeMsg(video_note=object())) == "video_note"
        assert Bridge._tg_kind(FakeMsg(voice=object())) == "voice"
        assert Bridge._tg_kind(FakeMsg(audio=object())) == "audio"
        assert Bridge._tg_kind(FakeMsg(gif=object())) == "animation"
        assert Bridge._tg_kind(FakeMsg(sticker=object())) == "sticker"
        assert Bridge._tg_kind(FakeMsg(document=object())) == "document"

    def test_specials(self):
        poll_media = tg_t.MessageMediaPoll(poll=None, results=None)
        assert Bridge._tg_kind(FakeMsg(media=poll_media)) == "poll"
        dice = tg_t.MessageMediaDice(emoticon="🎲", value=3)
        assert Bridge._tg_kind(FakeMsg(media=dice)) == "dice"
        contact = tg_t.MessageMediaContact(phone_number="1", first_name="a",
                                           last_name="", user_id=0, vcard="")
        assert Bridge._tg_kind(FakeMsg(media=contact)) == "contact"
        geo = tg_t.MessageMediaGeo(geo=tg_t.GeoPoint(lat=1.0, long=2.0, access_hash=0))
        assert Bridge._tg_kind(FakeMsg(media=geo)) == "location"

    def test_service_and_unsupported(self):
        class Act:
            pass
        assert Bridge._tg_kind(FakeMsg(action=Act())) == "service"
        assert Bridge._tg_kind(FakeMsg()) == "unsupported"


class TestBaleContent:
    def test_text(self):
        assert Bridge._bale_content({"text": "hi"})["kind"] == "text"

    def test_photo_picks_largest(self):
        c = Bridge._bale_content({"photo": [{"file_id": "a", "file_size": 1},
                                            {"file_id": "b", "file_size": 9}],
                                 "caption": "کپ"})
        assert c["kind"] == "photo" and c["file_id"] == "b" and c["text"] == "کپ"

    def test_animation_beats_document(self):
        c = Bridge._bale_content({"animation": {"file_id": "g"}, "document": {"file_id": "d"}})
        assert c["kind"] == "animation"

    def test_location_contact(self):
        loc = Bridge._bale_content({"location": {"latitude": 1, "longitude": 2}})
        assert loc["kind"] == "location"
        assert Bridge._bale_content({"contact": {"phone_number": "9"}})["kind"] == "contact"


class TestBaleAPI:
    def test_urls(self):
        api = BaleAPI("123:abc")
        assert api.url("getMe") == "https://tapi.bale.ai/bot123:abc/getMe"
        assert api.file_url("fp") == "https://tapi.bale.ai/file/bot123:abc/fp"

    def test_custom_base(self):
        api = BaleAPI("t", base="https://tapi.bale.ai/business/")
        assert api.url("sendMessage").startswith("https://tapi.bale.ai/business/bott/sendMessage")


class TestAdminParse:
    def make(self):
        return Admin.__new__(Admin)

    def test_slash_commands(self):
        a = self.make()
        assert a._parse("/add @a @b both") == ("add", ["@a", "@b", "both"])
        assert a._parse("/start@my_bot")[0] == "help"

    def test_persian_aliases(self):
        a = self.make()
        assert a._parse("لیست")[0] == "list"
        assert a._parse("راهنما")[0] == "help"
        assert a._parse("حذف 3")[0] == "remove"

    def test_unknown(self):
        a = self.make()
        assert a._parse("hello") == (None, [])
        assert a._parse("") == (None, [])


def test_fingerprint():
    assert _fp("text", "x") == _fp("text", "x")
    assert _fp("text", "x") != _fp("photo", "x")
