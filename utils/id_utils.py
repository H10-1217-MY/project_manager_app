import uuid
from datetime import datetime


class IdUtils:
    @staticmethod
    def generate_project_id() -> str:
        dt = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = uuid.uuid4().hex[:4]
        return f"PJT_{dt}_{suffix}"