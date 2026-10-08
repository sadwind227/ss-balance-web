"""源码运行入口，也是单文件程序的服务／计算子进程分流入口。"""

import sys
from app.server import main
from app.worker import main as worker_main

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--worker":
        worker_main(sys.argv[2:])
    else:
        main(open_browser="--no-browser" not in sys.argv[1:])
