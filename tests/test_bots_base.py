import chambaflow.bots.base as base
from chambaflow.bots.occ import BotOCC


class FakeDriver:
    def __init__(self, page_text):
        self.page_text = page_text
        self.visited = []

    def get(self, url):
        self.visited.append(url)

    def execute_script(self, script):
        return self.page_text


class BrokenDriver:
    def get(self, url):
        raise RuntimeError("navegador cerrado")


def _bot(monkeypatch, page_text):
    monkeypatch.setattr(base, "get_random_delay", lambda *a, **k: None)
    return BotOCC(FakeDriver(page_text))


def test_is_logged_in_true_when_only_logged_in_signal(monkeypatch):
    bot = _bot(monkeypatch, "bienvenido juan | cerrar sesión | mis postulaciones")
    assert bot.is_logged_in() is True


def test_is_logged_in_false_when_only_logged_out_signal(monkeypatch):
    bot = _bot(monkeypatch, "inicia sesión para continuar | regístrate gratis")
    assert bot.is_logged_in() is False


def test_is_logged_in_none_when_ambiguous(monkeypatch):
    bot = _bot(monkeypatch, "vacantes de empleo en méxico")
    assert bot.is_logged_in() is None


def test_is_logged_in_none_when_both_signals_present(monkeypatch):
    # Pagina con banner "inicia sesion" residual pero tambien "cerrar sesion"
    # visible (ej. layout con ambos textos en el DOM): no confiar, marcar None.
    bot = _bot(monkeypatch, "cerrar sesión ... inicia sesión")
    assert bot.is_logged_in() is None


def test_is_logged_in_none_on_navigation_error(monkeypatch):
    monkeypatch.setattr(base, "get_random_delay", lambda *a, **k: None)
    bot = BotOCC(BrokenDriver())
    assert bot.is_logged_in() is None


def test_is_logged_in_none_when_no_login_check_url(monkeypatch):
    monkeypatch.setattr(base, "get_random_delay", lambda *a, **k: None)

    class BotSinLogin(base.BotBase):
        sitio = "SinLogin"

    bot = BotSinLogin(FakeDriver("cerrar sesión"))
    assert bot.is_logged_in() is None
