# 整数平衡化工具

面向使用者的纯文本说明见 [README.txt](README.txt)。已打包的 Windows 64 位程序将在 [GitHub Releases](https://github.com/sadwind227/ss-balance-web/releases) 页面提供：完整解压后双击文件夹内的 `整数平衡化.exe`，无需安装 Python。构建记录见 [打包记录](docs/06-打包记录.md)。

这是一个在本机浏览器使用的整数平衡化程序。输入十进制整数后，它会判断能否在原有数字串中插入 `+ - * /`、括号和等号，生成正确的等式。数字及其顺序不会改变；每条展示的等式都会经过独立的精确分数验证。

例如，输入 `1234` 可得到 `12=3 * 4`；输入 `222` 并选择“允许多个等号”可得到 `2=2=2`。项目报告的最大反例 `9989858` 会显示为无法平衡化。

## 启动

从源码运行需要 **Python 3.10 或更高版本**，运行时只使用标准库。进入本目录，执行：

```powershell
python run.py
```

程序会自动打开本地网页。保持终端窗口开启即可继续使用；按 `Ctrl+C` 关闭。若网页未自动打开，终端会显示 `http://127.0.0.1:端口/`，把该地址复制到浏览器即可。

Windows 用户也可双击 [启动工具.bat](启动工具.bat)。无需登录或把输入上传到外部服务器。

重建 Windows 程序：先执行 `python tools/install_build_deps.py`，再执行 `python tools/build_release.py`。构建依赖只放在工程目录的隐藏构建文件夹中，不进入发布包。

## 功能与规则

- 默认寻找**恰好一个等号**的方案；可改为允许多个等号。
- 默认规则允许每个等号段的首个数词带前导负号；严格规则禁用前导负号。
- 默认请求 5 条方案，最多请求 20 条。找到的方案逐条展示，数量可能少于请求数量。
- 对 16 位及以上整数，优先通过短归零子串构造 `0=0` 型等式。
- 允许取消长时间搜索；搜索超时或达到资源上限时，不会因此误报“无解”。
- 输入限非负十进制整数、无多位先导零、最长 256 位。这个长度限制是程序的资源边界，不是定理限制。

单等号存在性及短整数反例分类来自上游公开数据；严格规则下的多等号弱例会重新计算。软件把“根据上游数据或定理已知存在”和“已生成且验证等式”分别显示。

## 工程目录

| 路径 | 内容 |
|---|---|
| `app/` | 本地 HTTP 服务、计算任务与后台子进程 |
| `engine/` | 数据校验、搜索、构造与独立等式验证 |
| `web/` | HTML、CSS 和前端交互 |
| `vendor/upstream/` | 固定的上游源码、数据与 MIT 许可 |
| `tests/` | 本应用测试 |
| `tools/` | 上游测试的本地运行辅助工具 |
| `docs/` | 原工程规划与实现记录 |

## 验证

```powershell
python -m unittest discover -s tests -v
python tools/check_upstream.py
python vendor/upstream/verify_results.py
```

本次实施中，本应用 **10 项测试通过**，上游 **19 项测试通过**，上游默认验证 **41 项检查通过**。测试包括上游数据散列、数学规则、短串多方案、长串构造、本地网页接口和访问边界。尚未重新完成约 8200 万候选的全量筛选，也不把上游数据清单散列等同于独立数学证明。

## 上游来源和许可

[Silicon-Silence-s-Balance-Integer-Theorem-Proof-and-Verification-Program](https://github.com/guijixzh/Silicon-Silence-s-Balance-Integer-Theorem-Proof-and-Verification-Program)，固定提交 `5d849da7f78e21affb2999257edfd71a7676baf3`。来源与本地数据校验细节见 [实现与验证记录](docs/05-实现与验证.md)。上游代码和数据按其 [MIT 许可](vendor/upstream/LICENSE)保留。

原工程规划文档：[需求规格](docs/01-需求规格.md)、[技术设计](docs/02-技术设计.md)、[开发计划](docs/03-开发计划.md)、[决策与来源](docs/04-决策与来源.md)。
