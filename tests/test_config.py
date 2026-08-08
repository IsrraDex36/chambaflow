from chambaflow.config import ensure_config_exists, load_config


def test_ensure_config_exists_copies_template_when_missing(tmp_path):
    template = tmp_path / "config.example.yaml"
    template.write_text("sitios: [\"occ\"]\nbrowser: \"brave\"\n", encoding="utf-8")
    config_path = tmp_path / "config.yaml"

    created = ensure_config_exists(str(config_path), template_path=str(template))

    assert created is True
    assert config_path.is_file()
    assert load_config(str(config_path)) == {"sitios": ["occ"], "browser": "brave"}


def test_ensure_config_exists_does_not_overwrite_existing(tmp_path):
    template = tmp_path / "config.example.yaml"
    template.write_text("browser: \"chrome\"\n", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("browser: \"brave\"\n", encoding="utf-8")

    created = ensure_config_exists(str(config_path), template_path=str(template))

    assert created is False
    assert load_config(str(config_path)) == {"browser": "brave"}


def test_ensure_config_exists_noop_when_template_missing(tmp_path):
    config_path = tmp_path / "config.yaml"
    template_path = tmp_path / "no_existe.yaml"

    created = ensure_config_exists(str(config_path), template_path=str(template_path))

    assert created is False
    assert not config_path.exists()


def test_default_template_path_points_to_real_file():
    from chambaflow.config import DEFAULT_TEMPLATE_PATH
    import os
    assert os.path.isfile(DEFAULT_TEMPLATE_PATH)
