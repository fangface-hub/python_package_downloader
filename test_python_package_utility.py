import tarfile
import zipfile

import pytest

import python_package_utility as u


@pytest.mark.parametrize("text,expected", [
    ("requests", ("requests", "")),
    ("requests>=2.0", ("requests", ">=2.0")),
    ("pkg==1.0.0rc1", ("pkg", "==1.0.0rc1")),
    ("foo(>=1.0)", ("foo", ">=1.0")),
])
def test_parse_package_condition(text, expected):
    req = u.parse_package_condition(text)
    assert (req.package_name, req.version_condition) == expected


@pytest.mark.parametrize("text", ["", "# comment", "bad!!x"])
def test_parse_package_condition_invalid(text):
    assert u.parse_package_condition(text) is None


def test_version_satisfies():
    assert u.version_satisfies("1.0", "")
    assert u.version_satisfies("1.0.0rc1", "==1.0.0rc1")
    assert not u.version_satisfies("2.0", "!=2.0")


def test_find_packages_normalizes_names(tmp_path):
    for name in ("my_pkg-1.0-py3-none-any.whl",
                 "my_pkg_extra-1.0-py3-none-any.whl", "My.Pkg-2.0.tar.gz"):
        (tmp_path / name).touch()
    req = u.PackageRequirements("my-pkg", ">=1.0")
    assert len(u.find_whl_package_info_list(str(tmp_path), "my-pkg")) == 1
    assert u.check_whl_version(str(tmp_path), req, "any", "3.11")
    assert u.check_targz(str(tmp_path), req)


def test_load_settings_survives_undecryptable_password(tmp_path, monkeypatch):
    monkeypatch.setattr(u, "DATA_DIR", tmp_path)
    (tmp_path / "settings.json").write_text('{"proxy_password": "broken"}')
    assert u.load_settings()["proxy_password"] == ""


def test_extract_license(tmp_path):
    whl = tmp_path / "foo-1.0-py3-none-any.whl"
    with zipfile.ZipFile(whl, "w") as z:
        z.writestr("foo-1.0.dist-info/LICENSE", "MIT")
    lic = tmp_path / "out"
    lic.mkdir()
    u.extract_license_from_package(str(whl), str(lic))
    assert (lic / "foo-1.0_LICENSE.txt").read_text() == "MIT"

    tgz = tmp_path / "bar-2.0.tar.gz"
    src = tmp_path / "COPYING"
    src.write_text("GPL")
    with tarfile.open(tgz, "w:gz") as t:
        t.add(src, arcname="bar-2.0/COPYING")
    u.extract_license_from_package(str(tgz), str(lic))
    assert (lic / "bar-2.0_LICENSE.txt").read_text() == "GPL"


class _Pkg:
    def __init__(self, filename, yanked=False):
        self.filename = filename
        self.url = f"https://example.invalid/{filename}"
        self.is_yanked = yanked


def test_select_latest_package_respects_platform_python_and_version():
    pkgs = [
        _Pkg("foo-1.0-cp311-cp311-win_amd64.whl"),
        _Pkg("foo-2.0-cp311-cp311-win_amd64.whl"),
        _Pkg("foo-3.0-cp311-cp311-win_amd64.whl", yanked=True),
        _Pkg("foo-2.5-cp312-cp312-win_amd64.whl"),
        _Pkg("foo-2.6-cp311-cp311-manylinux2014_x86_64.whl"),
        _Pkg("foo-1.5-py3-none-any.whl"),
        _Pkg("foo-2.0.tar.gz"),
    ]
    req = u.PackageRequirements("foo", "<2.5")
    best = u._select_latest_package(pkgs, req, "win_amd64", "3.11")
    assert best.filename == "foo-2.0-cp311-cp311-win_amd64.whl"
    best = u._select_latest_package(pkgs, req, "linux_aarch64", "3.11")
    assert best.filename == "foo-1.5-py3-none-any.whl"
    assert u._select_latest_package(pkgs, req).filename == "foo-2.0.tar.gz"


@pytest.fixture
def memory_keyring():
    import keyring
    from keyring.backend import KeyringBackend

    class Memory(KeyringBackend):
        priority = 1

        def __init__(self):
            self.store = {}

        def get_password(self, service, username):
            return self.store.get((service, username))

        def set_password(self, service, username, password):
            self.store[(service, username)] = password

        def delete_password(self, service, username):
            self.store.pop((service, username), None)

    previous = keyring.get_keyring()
    backend = Memory()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


def test_generate_key_uses_keyring_and_migrates_key_file(
        tmp_path, monkeypatch, memory_keyring):
    monkeypatch.setattr(u, "DATA_DIR", tmp_path)
    old_key = u.Fernet.generate_key()
    (tmp_path / "key.key").write_bytes(old_key)

    assert u.generate_key() == old_key
    assert not (tmp_path / "key.key").exists()
    assert u.generate_key() == old_key  # keyringから取得


def test_generate_key_creates_key_in_keyring_only(tmp_path, monkeypatch,
                                                  memory_keyring):
    monkeypatch.setattr(u, "DATA_DIR", tmp_path)
    key = u.generate_key()
    assert not (tmp_path / "key.key").exists()
    assert u.generate_key() == key


def test_generate_key_falls_back_to_file(tmp_path, monkeypatch):
    from keyring.errors import NoKeyringError

    def fail(*args, **kwargs):
        raise NoKeyringError("none")

    monkeypatch.setattr(u, "DATA_DIR", tmp_path)
    monkeypatch.setattr(u.keyring, "get_password", fail)
    key = u.generate_key()
    assert (tmp_path / "key.key").read_bytes() == key


def test_extract_license_saves_all_and_ignores_unrelated(tmp_path):
    whl = tmp_path / "foo-1.0-py3-none-any.whl"
    with zipfile.ZipFile(whl, "w") as z:
        z.writestr("foo-1.0.dist-info/licenses/LICENSE", "MIT")
        z.writestr("foo-1.0.dist-info/licenses/LICENSE.third", "BSD")
        z.writestr("foo-1.0.dist-info/METADATA", "x")
    out = tmp_path / "out"
    out.mkdir()
    u.extract_license_from_package(str(whl), str(out))
    assert sorted(p.name for p in out.iterdir()) == [
        "foo-1.0_LICENSE.txt", "foo-1.0_LICENSE_2.txt"
    ]


def test_dependencies_are_filtered_by_config_history(tmp_path):
    whl = tmp_path / "foo-1.0-py3-none-any.whl"
    with zipfile.ZipFile(whl, "w") as z:
        z.writestr("foo-1.0.dist-info/METADATA",
                   "Requires-Dist: bar>=1.0\nRequires-Dist: baz\n")
    history = [u.PackageRequirements("baz", "")]
    deps = u.get_dependencies_from_whl(str(whl), history)
    assert [d.package_name for d in deps] == ["bar"]
    assert history == [u.PackageRequirements("baz", "")]
    assert u.DownloadConfig().history is not u.DownloadConfig().history


@pytest.mark.parametrize("name,ver,ok", [
    ("a-1-py3-none-any.whl", "3.11", True),
    ("a-1-cp311-cp311-win_amd64.whl", "3.11", True),
    ("a-1-cp37-abi3-win_amd64.whl", "3.11", True),
    ("a-1-cp312-abi3-win_amd64.whl", "3.11", False),
    ("a-1-cp312-cp312-win_amd64.whl", "3.11", False),
    ("a-1-cp313-cp313t-win_amd64.whl", "3.13", False),
    ("a-1-py310-none-any.whl", "3.9", False),
    ("a-1-py2.py3-none-any.whl", "3.11", True),
])
def test_is_python_compatible(name, ver, ok):
    info = u.get_package_info_from_whl(name)
    assert u.is_python_compatible(info, ver) is ok


def _cli_setup(monkeypatch, tmp_path, run):
    monkeypatch.setattr(u, "run_command", run)
    monkeypatch.setattr(u, "_resolve_pip_command_prefix", lambda p: ["pip"])
    monkeypatch.setattr(u, "OS_TO_PLATFORMS", {"X": ["p1", "p2"]})
    return u.DownloadConfig(os_list=["X"], python_versions=["3.11", "3.12"],
                            dest_folder=str(tmp_path))


def test_cli_failure_continues_with_other_combinations(tmp_path, monkeypatch):
    import subprocess
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        raise subprocess.CalledProcessError(1, cmd)

    cfg = _cli_setup(monkeypatch, tmp_path, run)
    u.download_package_pip(u.PackageRequirements("foo", ""), cfg)
    assert len(calls) == 4
    assert not cfg.disabled_tools


def test_cli_usage_error_disables_tool_and_falls_back(tmp_path, monkeypatch):
    import subprocess
    calls, fallback = [], []

    def run(cmd, **kw):
        calls.append(cmd)
        raise subprocess.CalledProcessError(2, cmd)

    cfg = _cli_setup(monkeypatch, tmp_path, run)
    monkeypatch.setattr(u, "PYPISIMPLE_AVAILABLE", True)
    monkeypatch.setattr(u, "download_package_no_pip",
                        lambda *a, **k: fallback.append(a))
    req = u.PackageRequirements("foo", "")
    u.download_package_pip(req, cfg)
    u.download_package_pip(req, cfg)
    assert len(calls) == 1  # 2回目以降はpipを実行しない
    assert len(fallback) == 2
    assert "pip" in cfg.disabled_tools


def test_failed_combination_is_not_retried_across_nested_configs(
        tmp_path, monkeypatch):
    import subprocess
    from dataclasses import replace
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        raise subprocess.CalledProcessError(1, cmd)

    cfg = _cli_setup(monkeypatch, tmp_path, run)
    req = u.PackageRequirements("foo", ">=1")
    u.download_package_pip(req, cfg)
    nested = replace(cfg, dependency_level=1)  # 依存関係用のconfig
    u.download_package_pip(req, nested)
    assert len(calls) == 4
