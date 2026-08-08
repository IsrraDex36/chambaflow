import chambaflow.browser_detect as bd


def test_detect_os_maps_platform_system(monkeypatch):
    monkeypatch.setattr(bd.platform, "system", lambda: "Darwin")
    assert bd.detect_os() == "macOS"

    monkeypatch.setattr(bd.platform, "system", lambda: "Windows")
    assert bd.detect_os() == "Windows"

    monkeypatch.setattr(bd.platform, "system", lambda: "Linux")
    assert bd.detect_os() == "Linux"

    monkeypatch.setattr(bd.platform, "system", lambda: "FreeBSD")
    assert bd.detect_os() == "FreeBSD"  # SO desconocido: devuelve crudo, no revienta


def test_find_browser_path_returns_first_existing_candidate(monkeypatch):
    monkeypatch.setattr(bd.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(bd.os.path, "exists", lambda p: p == "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser")
    assert bd.find_browser_path("brave") == "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"


def test_find_browser_path_none_when_nothing_installed(monkeypatch):
    monkeypatch.setattr(bd.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(bd.os.path, "exists", lambda p: False)
    assert bd.find_browser_path("chrome") is None


def test_find_browser_path_unknown_browser_name(monkeypatch):
    monkeypatch.setattr(bd.platform, "system", lambda: "Linux")
    monkeypatch.setattr(bd.os.path, "exists", lambda p: True)
    assert bd.find_browser_path("edge") is None


def test_detect_available_browsers_shape(monkeypatch):
    monkeypatch.setattr(bd.platform, "system", lambda: "Linux")
    monkeypatch.setattr(bd.os.path, "exists", lambda p: "brave" in p)
    result = bd.detect_available_browsers()
    assert result["brave"] is not None
    assert result["chrome"] is None
    assert set(result.keys()) == {"brave", "chrome"}
