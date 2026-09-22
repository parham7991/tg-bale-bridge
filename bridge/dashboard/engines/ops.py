"""موتور عملیات ویژه — پروب واقعی دسترسی + ادمین‌کردن ربات توسط سلف بله.

همان موتورهایی که دستورات /access و /promote بات استفاده می‌کنند؛ اینجا فقط
نتیجه به‌صورت متن گزارش برمی‌گردد (لایهٔ API آن را JSON می‌کند).
"""
from __future__ import annotations

from ...bot_api import BotAPI
from ...wizard import probe_bale_access, probe_tg_access
from ..context import RuntimeCtx
from .base import DashboardError


class OpsEngine:
    def __init__(self, ctx: RuntimeCtx) -> None:
        self.ctx = ctx

    # ------------------------------------------------------------ دسترسی
    async def access_report(self) -> str:
        pairs = self.ctx.db.list_pairs()
        if not pairs:
            raise DashboardError("جفتی ثبت نشده", 404)
        lines = ["🔓 دسترسی سلف‌ها به کانال‌ها:"]
        tg, bale = self.ctx.tg, self.ctx.bale
        for p in pairs:
            lines.append("")
            lines.append(f"🔗 جفت #{p['id']}: {p['tg_label'] or p['tg_chat_id']} ⇄ "
                         f"{p['bale_label'] or p['bale_chat_id']} ({p['mode']})")
            if tg is not None:
                try:
                    _, note = await probe_tg_access(tg, p["tg_chat_id"])
                except Exception as e:
                    note = f"✘ {str(e)[:60]}"
                lines.append(f"  ▫️ سلف تلگرام → {p['tg_label'] or p['tg_chat_id']}: {note}")
            else:
                lines.append("  ▫️ سلف تلگرام: — در دسترس نیست")
            if bale is not None:
                try:
                    _, note = await probe_bale_access(bale, p["bale_chat_id"])
                except Exception as e:
                    note = f"✘ {str(e)[:60]}"
                lines.append(f"  ▫️ سمت بله → {p['bale_label'] or p['bale_chat_id']}: {note}")
            else:
                lines.append("  ▫️ سمت بله: — در دسترس نیست")
        return "\n".join(lines)

    # ------------------------------------------------------------ ادمین‌کردن ربات
    async def promote_bot(self) -> str:
        from ...bale_user import BaleUserAPI

        bale = self.ctx.bale
        if not isinstance(bale, BaleUserAPI):
            raise DashboardError("این کار با سلف بله انجام می‌شود (BALE_MODE=user)", 409)
        bb = self.ctx.store.bale_bot()
        if not bb:
            raise DashboardError("ربات بله ثبت نشده — از ویزارد (🤖) ثبتش کنید", 409)
        me = bb.get("me") or {}
        bot_ref = me.get("username") or me.get("id")
        bot_api = BotAPI(bb["token"], getattr(self.ctx.cfg, "BALE_API_BASE",
                                              "https://tapi.bale.ai"))
        lines = ["🛡 نتیجهٔ ادمین‌کردن ربات بله:"]
        try:
            for p in self.ctx.db.list_pairs():
                label = p["bale_label"] or p["bale_chat_id"]
                try:
                    await bale.add_admin(p["bale_chat_id"], bot_ref)
                    note = "✔ اضافه و ادمین شد"
                    try:
                        ok, pnote = await probe_bale_access(bot_api, p["bale_chat_id"])
                        note += " — تست ارسال: " + ("✔" if ok else f"✘ {pnote}")
                    except Exception as e:
                        note += f" — تست: ✘ {str(e)[:60]}"
                except Exception as e:
                    note = f"✘ {str(e)[:120]}"
                lines.append(f"  ▫️ {label}: {note}")
        finally:
            try:
                await bot_api.close()
            except Exception:
                pass
        return "\n".join(lines)
