import threading
import copy
from typing import Dict, List


class Aggregator:
    def __init__(self, systems: List[str], hubs: List[str]):
        self.lock = threading.Lock()
        self.systems = list(systems)
        self.hubs = list(hubs)
        self.aggregations = {
            k: {h: {hub: 0.0 for hub in hubs} for h in range(24)}
            for k in systems
        }

    def update(self, system: str, hour: int, hub: str, val: float) -> None:
        if system not in self.aggregations:
            raise KeyError(f"Unknown system: {system}")
        if not (0 <= hour < 24):
            raise ValueError(f"Invalid hour: {hour}")
        with self.lock:
            self.aggregations[system][hour][hub] += float(val)

    def snapshot(self) -> Dict:
        with self.lock:
            return copy.deepcopy(self.aggregations)

    def get(self, system: str, hour: int, hub: str) -> float:
        with self.lock:
            return self.aggregations[system][hour][hub]
