import os
import time

from chambaflow.driver import cleanup_old_screenshots


def _touch(path, age_days):
    with open(path, "w", encoding="utf-8") as f:
        f.write("fake png")
    old_time = time.time() - age_days * 86400
    os.utime(path, (old_time, old_time))


def test_cleanup_removes_only_old_png_files(tmp_path):
    old_png = tmp_path / "occ_fail_old.png"
    new_png = tmp_path / "occ_fail_new.png"
    old_log = tmp_path / "occ_apply_failures.log"

    _touch(old_png, age_days=45)
    _touch(new_png, age_days=1)
    _touch(old_log, age_days=45)  # los .log nunca se tocan, sin importar edad

    removed = cleanup_old_screenshots(str(tmp_path), max_age_days=30)

    assert removed == 1
    assert not old_png.exists()
    assert new_png.exists()
    assert old_log.exists()


def test_cleanup_disabled_when_max_age_not_positive(tmp_path):
    old_png = tmp_path / "occ_fail_old.png"
    _touch(old_png, age_days=999)

    assert cleanup_old_screenshots(str(tmp_path), max_age_days=0) == 0
    assert cleanup_old_screenshots(str(tmp_path), max_age_days=-5) == 0
    assert old_png.exists()


def test_cleanup_missing_directory_is_noop(tmp_path):
    assert cleanup_old_screenshots(str(tmp_path / "no_existe"), max_age_days=30) == 0
