from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from .models import UserState


class JsonStorage:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def _read_all(self) -> dict[str, dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def get_user_state(self, user_id: int) -> UserState:
        data = self._read_all()
        user_data = data.get(str(user_id))
        return UserState.from_dict(user_data) if user_data else UserState()

    def save_user_state(self, user_id: int, state: UserState) -> None:
        with self._lock:
            data = self._read_all()
            data[str(user_id)] = state.to_dict()
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
