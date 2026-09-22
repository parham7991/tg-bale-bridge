"""پیکربندی برنامه — شیم بستهٔ bridge/appcfg (از v2.16.0).

همهٔ منطق (خواندن .env، مسیرها، بخش‌ها، اعتبارسنجی) در ``bridge/appcfg/`` است؛
این ماژول فقط مقادیر را در فضای‌نام خودش تزریق می‌کند تا
``import config as cfg`` و ``cfg.X = ...`` مثل قبل کار کند.
"""
from bridge.appcfg import populate

populate(globals())
