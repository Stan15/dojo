from typing import Any, List, Dict, Optional
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

    # ==========================================
    # AI Connector Operations
    # ==========================================
    def list_connectors(self) -> List[Dict[str, Any]]:
        conn_dir = self.engine.dojo_dir / "connectors"
        if not conn_dir.exists():
            return []
        connectors = []
        for f in conn_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data.setdefault("name", f.stem)
                    connectors.append(data)
            except Exception:
                pass
        return connectors

    def get_connector(self, name: str) -> Optional[Dict[str, Any]]:
        filepath = self.engine.dojo_dir / "connectors" / f"{name}.yaml"
        if not filepath.exists():
            return None
        try:
            data = yaml.safe_load(filepath.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("name", name)
                return data
        except Exception:
            pass
        return None

    def save_connector(self, name: str, data: Dict[str, Any]):
        filepath = f"connectors/{name}.yaml"
        with self.engine.write_lock():
            self.engine.write_text(filepath, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))

    def delete_connector(self, name: str):
        filepath = f"connectors/{name}.yaml"
        with self.engine.write_lock():
            self.engine.delete_file(filepath)
