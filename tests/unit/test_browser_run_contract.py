from web_gui_agent.domain.ports.browser_run import BrowserRun, BrowserRunFactory


def test_browser_run_contracts_are_importable() -> None:
    assert BrowserRun.__name__ == "BrowserRun"
    assert BrowserRunFactory.__name__ == "BrowserRunFactory"
