# KStack repository instructions

Develop with Python 3.10+ standard library and no runtime dependencies. Work in feature branches where practical. Keep the system local-first, make no secret/network writes except explicit authorised delivery, do not execute external skill payloads, preserve existing file ownership, and never report unrun checks as passing.

Run `python -m unittest discover -s tests -v` with `PYTHONPATH=src` and `python scripts/kstack.py doctor` before delivery. Network tests must be mocked. GitHub Actions are not available; do not depend on them or attempt hosted CI merely for verification. New auto-adoption logic must retain immutable commit pins, independent evidence reviews, security gates and rollback.
