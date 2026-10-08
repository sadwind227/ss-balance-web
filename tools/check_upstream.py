"""运行上游单元测试，并规避受限 Windows 环境的临时目录 ACL 问题。

上游测试使用 tempfile.TemporaryDirectory()。本环境的 tempfile 默认 mode=0700
在创建后会阻止测试写入；我们只替换目录创建方式，不修改上游测试本身。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMP_ROOT = ROOT / ".test_tmp"
TEMP_ROOT.mkdir(exist_ok=True)


def workspace_mkdtemp(suffix=None, prefix=None, dir=None):
    path = TEMP_ROOT / f"{prefix or 'tmp'}{uuid.uuid4().hex}{suffix or ''}"
    path.mkdir(mode=0o777)
    return str(path)


tempfile.mkdtemp = workspace_mkdtemp
sys.path.insert(0, str(ROOT / "vendor/upstream"))
suite = unittest.defaultTestLoader.discover(str(ROOT / "vendor/upstream/tests"))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
