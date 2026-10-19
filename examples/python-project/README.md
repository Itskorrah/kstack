# Disposable Python acceptance fixture

Used to demonstrate KStack's **actual local project inspection and execution of trusted tests**. It is not evidence that an external coding model invoked a skill.

From the KStack repository root:

```bash
python scripts/kstack.py inspect-project --project examples/python-project
python scripts/kstack.py route 'Validate records and run regression tests' --project examples/python-project
python scripts/kstack.py verify-project --project examples/python-project          # preview
python scripts/kstack.py verify-project --project examples/python-project --run    # real tests
```

Keep this fixture deterministic and offline. Do not copy a real user's private records into it.
