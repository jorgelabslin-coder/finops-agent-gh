import json
from datetime import date
from pathlib import Path


class SnapshotManager:
    def __init__(self, snapshots_dir: str):
        self.snapshots_dir = Path(snapshots_dir)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def save(self, dt: date, data: list[dict]):
        path = self.snapshots_dir / f"snapshot-{dt.isoformat()}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def load(self, dt: date) -> list[dict] | None:
        path = self.snapshots_dir / f"snapshot-{dt.isoformat()}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_snapshots(self) -> list[str]:
        return sorted(
            [p.stem.replace("snapshot-", "") for p in self.snapshots_dir.glob("snapshot-*.json")],
            reverse=True,
        )
