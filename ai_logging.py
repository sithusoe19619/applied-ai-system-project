from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
import json
import uuid


class AIRunLogger:
    """Persist a JSON trace for each AI planning run."""

    def __init__(self, log_dir: Path | None = None):
        base_dir = Path(__file__).resolve().parent
        self.log_dir = log_dir or base_dir / "logs"

    def log_run(self, payload: Dict[str, Any]) -> Path:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.log_dir / f"pawpal_ai_run_{timestamp}_{uuid.uuid4().hex[:8]}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
