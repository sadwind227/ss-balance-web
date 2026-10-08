# Integer Balance Tool

[中文](README.md) | [English](README_EN.md)

A local web application for checking whether a decimal digit string can be turned into a valid equation by inserting `+`, `-`, `*`, `/`, parentheses, and equals signs. It preserves every input digit in order and independently verifies each displayed equation using exact rational arithmetic.

The interface runs in your browser while a Python engine performs the search on your computer. Inputs are not sent to an external server.

For the Chinese plain-text user guide, see [README.txt](README.txt). A packaged Windows x64 build will be published on [GitHub Releases](https://github.com/sadwind227/ss-balance-web/releases) when available. Extract the full package and run `整数平衡化.exe`; Python is not required for the packaged build.

## Features

- Find equations with exactly one equals sign, or allow multiple equals signs.
- Choose the default rule, which permits a leading minus sign at the start of each equation segment, or strict mode, which forbids it.
- Request up to 20 distinct equation forms; fewer may be found within the search budget.
- For integers with 16 or more digits, prioritize constructions based on short zeroable substrings.
- Cancel a long search. A timeout or resource limit is reported as incomplete, never as proof that no solution exists.
- Accept non-negative decimal integers up to 256 digits, without multi-digit leading zeroes. The length limit is an application resource boundary, not a limit of the theorem.

For source-based use, the application uses the upstream published data for single-equals existence and short counterexample classification. Strict-mode weak cases with multiple equals are searched again. The interface distinguishes a solution known to exist from an equation that has already been generated and verified.

## Run from source

Requires Python 3.10 or later. The runtime uses only the Python standard library.

```powershell
python run.py
```

The application opens in your browser. Keep the terminal open while using it; press `Ctrl+C` to stop the local service. If the browser does not open automatically, copy the `http://127.0.0.1:<port>/` address printed in the terminal.

On Windows, you can also double-click [启动工具.bat](启动工具.bat). To rebuild the Windows package, run:

```powershell
python tools/install_build_deps.py
python tools/build_release.py
```

Build dependencies are isolated in a hidden folder inside the project and are not included in the release package.

## Project layout

| Path | Contents |
|---|---|
| `app/` | Local HTTP service and background search process |
| `engine/` | Data checks, search, construction, and independent equation verification |
| `web/` | HTML, CSS, and browser interaction |
| `vendor/upstream/` | Pinned upstream source code, data, and MIT license |
| `tests/` | Tests for this application |
| `tools/` | Helpers for running upstream checks |
| `docs/` | Requirements, design decisions, implementation, and verification records |

## Verification

```powershell
python -m unittest discover -s tests -v
python tools/check_upstream.py
python vendor/upstream/verify_results.py
```

The implementation record reports 10 application tests, 19 upstream tests, and 41 upstream verification checks passing. The project has not independently rerun the full screening of approximately 82 million candidates; checksums and packaged data do not replace an independent review of the mathematical proof.

## Acknowledgements and upstream source

Special thanks to my friend [guijixzh (硅基飙尘葆光)](https://github.com/guijixzh), whose theorem, proof, published verification code, and datasets made this application possible. I appreciate his work and his sharing of the project for others to study and build upon.

This application is based on the upstream repository [Silicon-Silence's Balance Integer Theorem: Proof and Verification Program](https://github.com/guijixzh/Silicon-Silence-s-Balance-Integer-Theorem-Proof-and-Verification-Program), pinned to commit `5d849da7f78e21affb2999257edfd71a7676baf3`. The upstream source and data retain their [MIT license](vendor/upstream/LICENSE). Details about provenance and local data checks are in [the implementation and verification record](docs/05-实现与验证.md).

The original planning documents are available in Chinese: [requirements](docs/01-需求规格.md), [technical design](docs/02-技术设计.md), [development plan](docs/03-开发计划.md), and [decisions and sources](docs/04-决策与来源.md).
