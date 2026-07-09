"""User configuration: one flat `config.yaml` at the store root, re-read on
every access (no cache — the user edits it directly). Unreadable YAML degrades
to empty config rather than crashing."""

from typing import Any
import yaml
from .base import BaseRepository

class ConfigRepository(BaseRepository):
    """Flat key/value access over config.yaml (keys like `daily.packet_size`
    are literal dotted strings, not nesting)."""

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
        """A copy of the full config mapping."""
        return dict(self._read_config())

    def get_value(self, key: str, default: Any = None) -> Any:
        """One value with its native YAML type, or `default`."""
        return self._read_config().get(key, default)

    def set_value(self, key: str, value: Any):
        """Sets one key and rewrites config.yaml."""
        config = self._read_config()
        config[key] = value
        self._write_config(config)

    def get(self, key: str) -> str | None:
        """String-coerced variant of `get_value` (None stays None)."""
        val = self.get_value(key)
        return str(val) if val is not None else None

    def set(self, key: str, value: str):
        """String-typed alias of `set_value`."""
        self.set_value(key, value)
