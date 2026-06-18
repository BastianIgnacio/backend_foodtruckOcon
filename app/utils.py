from datetime import datetime, timezone, timedelta

SANTIAGO_TZ = timezone(timedelta(hours=-4))


def now_santiago() -> datetime:
    return datetime.now(SANTIAGO_TZ)
