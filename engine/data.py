"""载入并核验固定的上游数据快照。"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

# PyInstaller 的单文件程序把随包资源解到 _MEIPASS；源码运行则使用工程目录。
ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "vendor" / "upstream" / "data"


class PublishedData:
    """清单哈希、条数及关键集合关系通过后才提供判定数据。"""

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in manifest["sha256"].items():
            actual = hashlib.sha256((data_dir / name).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f"上游数据校验失败：{name}")

        def read(name: str):
            return json.loads((data_dir / name).read_text(encoding="utf-8"))

        self.prime_zeroable = frozenset(read("prime_zeroable.json"))
        self.non_zeroable = frozenset(read("non_zeroable.json"))
        self.non_single = frozenset(read("non_balanceable.json"))
        self.strong = frozenset(read("strong_non_balanceable.json"))
        self.weak = frozenset(read("weak_non_balanceable.json"))
        self.classification = read("classification.json")

        counts = manifest["counts"]
        for name, collection in (
            ("prime_zeroable", self.prime_zeroable),
            ("non_zeroable", self.non_zeroable),
            ("non_balanceable", self.non_single),
            ("strong_non_balanceable", self.strong),
            ("weak_non_balanceable", self.weak),
            ("classification", self.classification),
        ):
            if len(collection) != counts[name]:
                raise ValueError(f"上游数据条数错误：{name}")
        if self.strong & self.weak or self.strong | self.weak != self.non_single:
            raise ValueError("上游反例集合关系错误")
        if set(self.classification) != self.non_single:
            raise ValueError("上游分类表范围错误")
        for number, witness in self.classification.items():
            if (witness is None) != (number in self.strong):
                raise ValueError(f"上游分类表记录错误：{number}")
        self.manifest = manifest


_cached: PublishedData | None = None


def published() -> PublishedData:
    global _cached
    if _cached is None:
        _cached = PublishedData()
    return _cached
