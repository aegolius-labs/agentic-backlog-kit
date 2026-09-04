# Release-candidate validation evidence

This record includes the final Wave C release-candidate rerun on 2026-09-04.
The packaged runtime is rooted at commit `2978922`; the concurrent R02 evidence,
test-expectation, roadmap, and validation-record updates do not alter packaged
runtime code. The validation run itself made no GitHub or repository writes.
Approved live GitHub mutations and their non-destructive boundaries are recorded
separately in the R02 capability evidence.

## Results

| Check | Windows host | Ubuntu WSL |
| --- | ---: | ---: |
| Complete test suite | 163 passed | 163 passed |
| CLI help | passed | passed |
| R09 benchmark (`100`, `1,000`, `10,000`) | passed | passed |
| Build sdist and wheel | passed | passed |
| Reinstall wheel and run `abk --help` | passed | passed |

The 2026-09-04 Windows benchmark report is 9,421 bytes with SHA-256
`0c8e76542847797eda4d30c764476599cc253e1725fd339d889e83df846addf3`.
A second Windows run and the Linux run produced the same digest; it is also
identical to the 2026-08-27 baseline, and all budget failures were empty. The
compact baselines are recorded in
[benchmarks.md](benchmarks.md).

The earlier 2026-08-27 Windows build produced these recorded artifacts; the
2026-09-04 build/install smoke check also passed, but its disposable artifacts
were not retained as release evidence:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `agentic_backlog_kit-0.1.0-py3-none-any.whl` | 56,369 | `02812a3a577ea8ee5afa553a97b3c5a5d97c0e77e399fbc917bff07f52db6352` |
| `agentic_backlog_kit-0.1.0.tar.gz` | 72,917 | `6dd3d329bd87475d5d74a23b7c445b281056b06f53b9d27f7273fee70a30ebd6` |

## Linux route and limits

The host is Windows. A read-only WSL probe found Ubuntu 20.04.6 LTS running
as WSL 1; Docker Desktop was stopped and its Linux daemon pipe was absent. The
distro's system interpreter is Python 3.8.10, below this package's declared
Python `>=3.11` requirement. For this validation only, the published
CPython 3.11.16 `x86_64-unknown-linux-gnu` install-only archive from the
[20260825 python-build-standalone release](https://github.com/astral-sh/python-build-standalone/releases/tag/20260825)
was downloaded to `/tmp` and verified before use:

```text
sha256:25844eb97cdc72cdc78addaad0969ce3b2133a4de54bfcfa4d57f8a6d095eaab
```

The mounted checkout was tested with commands equivalent to the Linux CI
workflow:

```sh
PYTHONPATH=src /tmp/abk-rc-python311/python/bin/python3.11 -m unittest discover -s tests -v
/tmp/abk-rc-python311/python/bin/python3.11 scripts/backlog.py --help
/tmp/abk-rc-python311/python/bin/python3.11 scripts/benchmark.py --check
/tmp/abk-rc-python311/python/bin/python3.11 -m build
/tmp/abk-rc-python311/python/bin/python3.11 -m pip install --force-reinstall dist/*.whl
/tmp/abk-rc-python311/python/bin/abk --help
```

This is successful local Linux/WSL evidence, not a hosted GitHub Actions
result. The remaining R07 gate requires authority to publish the canonical
GitHub repository, push the candidate, and observe `.github/workflows/test.yml`
on a clean `ubuntu-latest` runner. Until that authority and remote exist, no
hosted Linux run URL or branch-protection result can be recorded.
