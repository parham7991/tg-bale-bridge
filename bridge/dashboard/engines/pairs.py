"""موتور جفت‌های کانال — CRUD با resolve واقعی (نه صرفاً ذخیرهٔ متن کاربر)."""
from __future__ import annotations

from ..context import RuntimeCtx
from .base import DashboardError

VALID_MODES = ("both", "tg2bale", "bale2tg")


class PairsEngine:
    def __init__(self, ctx: RuntimeCtx) -> None:
        self.ctx = ctx

    def _require_bridge(self) -> None:
        if self.ctx.admin is None:
            raise DashboardError("نصب ناقص است — اول ویزارد بات را کامل کنید", 409)

    def list(self) -> list[dict]:
        return [dict(p) for p in self.ctx.db.list_pairs()]

    async def add(self, tg_ref: str, bale_ref: str, mode: str) -> int:
        self._require_bridge()
        tg_ref, bale_ref = (tg_ref or "").strip(), (bale_ref or "").strip()
        if not tg_ref or not bale_ref:
            raise DashboardError("هر دو کانال لازم است", 400)
        if mode not in VALID_MODES:
            raise DashboardError("حالت نامعتبر — یکی از: both/tg2bale/bale2tg", 400)
        try:
            tg_id, tg_label, tg_user = await self.ctx.admin._resolve_tg(tg_ref)
        except DashboardError:
            raise
        except Exception as e:
            raise DashboardError(f"کانال تلگرام resolve نشد: {str(e)[:120]}", 400) from e
        try:
            bale_id, bale_label, bale_user = await self.ctx.admin._resolve_bale(bale_ref)
        except DashboardError:
            raise
        except Exception as e:
            raise DashboardError(f"کانال بله resolve نشد: {str(e)[:120]}", 400) from e
        return self.ctx.db.add_pair(tg_id, tg_label, tg_user,
                                    bale_id, bale_label, bale_user, mode)

    def set_mode(self, pair_id: int, mode: str) -> str:
        if mode not in VALID_MODES:
            raise DashboardError("حالت نامعتبر", 400)
        if not self.ctx.db.set_mode(int(pair_id), mode):
            raise DashboardError("جفت پیدا نشد", 404)
        return mode

    def remove(self, pair_id: int) -> None:
        if not self.ctx.db.remove_pair(int(pair_id)):
            raise DashboardError("جفت پیدا نشد", 404)
