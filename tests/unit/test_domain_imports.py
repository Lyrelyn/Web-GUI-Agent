from pathlib import Path


def test_domain_has_no_fastapi_or_playwright_dependency() -> None:
    domain_root = Path("src/web_gui_agent/domain")

    imported_text = "\n".join(
        path.read_text(encoding="utf-8") for path in domain_root.rglob("*.py")
    )

    assert "fastapi" not in imported_text.lower()
    assert "playwright" not in imported_text.lower()
