"""Architecture guard: the engine core stays pure (no I/O, no LLM, no shell deps).

Enforces the functional-core/imperative-shell boundary and Constitution Principles
I (Determinism) and the no-LLM scope for Block 1.
"""

from __future__ import annotations

import re

from tests.conftest import ROOT

ENGINE_DIR = ROOT / "engine"

FORBIDDEN_IMPORTS = (
    "import pandas",
    "import openpyxl",
    "import csv",
    "import requests",
    "import urllib",
    "import socket",
    "import anthropic",
    "import openai",
    "from data",        # engine must not depend on the data layer impls
    "from export",
    "from shell",
    "from config.loader",  # loader is I/O; engine may use config.schemas only
)


def _engine_sources():
    return sorted(ENGINE_DIR.glob("*.py"))


def test_engine_has_no_io_or_llm_imports():
    offenders = []
    for path in _engine_sources():
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_IMPORTS:
            if needle in text:
                offenders.append(f"{path.name}: {needle!r}")
    assert not offenders, f"engine purity violations: {offenders}"


def test_engine_does_not_open_files_or_network():
    pattern = re.compile(r"\bopen\s*\(|\.read_csv\(|\.to_excel\(|requests\.|urllib\.")
    offenders = []
    for path in _engine_sources():
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(path.name)
    assert not offenders, f"engine performs I/O in: {offenders}"
