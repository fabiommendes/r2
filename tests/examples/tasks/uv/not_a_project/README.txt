Deliberately not a Python project: there is no pyproject.toml in this
directory. It exists so the test suite can check that r2 rejects a
directory that isn't a recognizable project instead of crashing on it.
