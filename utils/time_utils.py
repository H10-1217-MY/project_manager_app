from datetime import datetime


class TimeUtils:
    @staticmethod
    def now_iso() -> str:
        return datetime.now().replace(microsecond=0).isoformat()

    @staticmethod
    def display(iso_str: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return iso_str