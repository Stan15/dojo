from typing import Any
import yaml
from .base import BaseRepository

class ConfigRepository(BaseRepository):
    # ==========================================
    # Config Values Operations
    # ==========================================
    def _read_config(self) -> dict[str, Any]:
        filepath = self.engine.dojo_dir / "config.yaml"
        if not filepath.exists():
            return {}
        try:
            return yaml.safe_load(filepath.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def _write_config(self, config: dict[str, Any]):
        with self.engine.write_lock():
            self.engine.write_text("config.yaml", yaml.safe_dump(config, sort_keys=False, allow_unicode=True))

    def all(self) -> dict[str, Any]:
        return dict(self._read_config())

    def get_value(self, key: str, default: Any = None) -> Any:
        return self._read_config().get(key, default)

    def set_value(self, key: str, value: Any):
        config = self._read_config()
        config[key] = value
        self._write_config(config)

    # Helper for DB-compatible config queries
    def get(self, key: str) -> str | None:
        val = self.get_value(key)
        return str(val) if val is not None else None

    def set(self, key: str, value: str):
        self.set_value(key, value)
