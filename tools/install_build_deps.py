"""仅用于构建：把 PyInstaller 装到工程内，不修改全局 Python 环境。

当前 Windows 沙箱中 tempfile 默认创建的 mode=0700 目录不能继续写入；
这里使用工作区内 mode=0777 目录，内容不进入发布包。
"""

from __future__ import annotations

import runpy
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMP = ROOT / ".buildtmp"
TEMP.mkdir(exist_ok=True)


def workspace_mkdtemp(suffix=None, prefix=None, dir=None):
    path = TEMP / f"{prefix or 'pip-'}{uuid.uuid4().hex}{suffix or ''}"
    path.mkdir(mode=0o777)
    return str(path)


tempfile.mkdtemp = workspace_mkdtemp
sys.argv = ["pip", "install", "--target", str(ROOT / ".buildtools"), "--no-cache-dir", "pyinstaller"]
runpy.run_module("pip", run_name="__main__")
