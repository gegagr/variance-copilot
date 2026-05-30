"""Architecture guard: thin routes, FastAPI-free service, no commentary built in the API (FR-003/007)."""

from __future__ import annotations

from pathlib import Path

ROUTES = [p for p in sorted(Path("api/routes").glob("*.py")) if p.name != "__init__.py"]
SERVICES = [p for p in sorted(Path("api/services").glob("*.py")) if p.name != "__init__.py"]


def test_services_do_not_import_fastapi():
    for path in SERVICES:
        text = path.read_text(encoding="utf-8")
        assert "import fastapi" not in text and "from fastapi" not in text, f"{path} imports FastAPI"


def test_api_layer_does_no_financial_arithmetic():
    for path in ROUTES + SERVICES:
        text = path.read_text(encoding="utf-8")
        assert "Decimal(" not in text, f"{path} constructs a Decimal figure"
        assert ".quantize(" not in text, f"{path} rounds a figure"


def test_api_builds_no_commentary():
    """Every served Question/Draft comes from Block 3, not the API (FR-007)."""
    for path in ROUTES + SERVICES:
        text = path.read_text(encoding="utf-8")
        # The API must not call Block 3's rendering/builders or fabricate commentary text.
        assert "render_output" not in text, f"{path} renders commentary"
        assert "build_draft" not in text and "build_question" not in text, f"{path} builds commentary"


def test_routes_delegate_to_service():
    for path in ROUTES:
        text = path.read_text(encoding="utf-8")
        assert "Depends(get_service)" in text, f"{path} does not delegate to the service layer"
