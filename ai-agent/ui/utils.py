"""
Timezone utilities — read TZ_OFFSET_HOURS from .env, expose now_local() for consistent timestamps.
"""
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / '.env', override=True)

_OFFSET_HOURS = int(os.getenv('TZ_OFFSET_HOURS', '7'))
_TZ = timezone(timedelta(hours=_OFFSET_HOURS))

# SQL offset string for SQLite: e.g. "+7 hours"
TZ_SQL = f"+{_OFFSET_HOURS} hours" if _OFFSET_HOURS >= 0 else f"{_OFFSET_HOURS} hours"


def now_local() -> datetime:
    """Current datetime in configured local timezone (UTC+TZ_OFFSET_HOURS)."""
    return datetime.now(_TZ)


def now_local_str() -> str:
    """Current datetime as 'YYYY-MM-DD HH:MM:SS' in local timezone."""
    return now_local().strftime('%Y-%m-%d %H:%M:%S')
