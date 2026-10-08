"""生成 Windows 独立程序文件夹和带 README.txt 的可分发 ZIP。

先运行 install_build_deps.py。构建工具只保存在 .buildtools 中；它不会被打包。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / ".buildtools"
DIST = ROOT / "dist"
NAME = "整数平衡化"


def main() -> None:
    if not (TOOLS / "PyInstaller").is_dir():
        raise SystemExit("先运行 python tools/install_build_deps.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(TOOLS) + os.pathsep + env.get("PYTHONPATH", "")
    add_data = [
        (ROOT / "web", "web"),
        (ROOT / "vendor/upstream/data", "vendor/upstream/data"),
        (ROOT / "vendor/upstream/sst_core.py", "vendor/upstream"),
    ]
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
            "--name", NAME, "--distpath", str(DIST),
            "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build")]
    for source, destination in add_data:
        args.extend(["--add-data", f"{source}{os.pathsep}{destination}"])
    args.append(str(ROOT / "run.py"))
    subprocess.run(args, cwd=ROOT, env=env, check=True)

    app_dir = DIST / NAME
    executable = app_dir / f"{NAME}.exe"
    if not executable.is_file():
        raise RuntimeError("构建结束但找不到可执行文件")
    shutil.copy2(ROOT / "README.txt", app_dir / "README.txt")
    shutil.copy2(ROOT / "vendor/upstream/LICENSE", app_dir / "LICENSE")
    archive = DIST / f"{NAME}-Windows-x64.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, allowZip64=True) as bundle:
        for source in sorted(app_dir.rglob("*")):
            if source.is_file():
                bundle.write(source, source.relative_to(DIST))
    print(f"发布包：{archive}")
    print(f"主程序：{executable}")


if __name__ == "__main__":
    main()
