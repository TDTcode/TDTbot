import types

import pytest

from TDTbot import reloader


def _make_module(name, file_path, children=None):
    mod = types.ModuleType(name)
    mod.__file__ = file_path
    mod.__package__ = "pkg"
    children = children or {}
    for attr, child in children.items():
        setattr(mod, attr, child)
    return mod


def test_reload_package_recurses_same_directory(monkeypatch):
    base_dir = "/tmp/pkg/"
    pkg = _make_module("pkg", f"{base_dir}__init__.py")
    child = _make_module("pkg.child", f"{base_dir}child.py")
    grandchild = _make_module("pkg.child.grand", f"{base_dir}grand.py")
    outside = _make_module("other", "/other/out.py")

    # Build hierarchy
    pkg.child = child
    pkg.outside = outside
    child.grandchild = grandchild

    reloaded = []

    def fake_reload(module):
        reloaded.append(module.__file__)
        return module

    monkeypatch.setattr(reloader.importlib, "reload", fake_reload)

    reloader.reload_package(pkg)

    # Parent and in-directory descendants reloaded
    assert f"{base_dir}__init__.py" in reloaded
    assert f"{base_dir}child.py" in reloaded
    assert f"{base_dir}grand.py" in reloaded
    # Outside module should not be reloaded
    assert "/other/out.py" not in reloaded


def test_reload_package_deduplicates_and_ignores_non_modules(monkeypatch):
    base_dir = "/tmp/pkg/"
    pkg = _make_module("pkg", f"{base_dir}__init__.py")
    dup_child = _make_module("pkg.child", f"{base_dir}child.py")

    # Reference same child twice to ensure deduplication
    pkg.first = dup_child
    pkg.second = dup_child
    pkg.not_a_module = {"__file__": f"{base_dir}fake.py"}  # should be ignored

    reloaded = []

    def fake_reload(module):
        reloaded.append(module.__file__)
        return module

    monkeypatch.setattr(reloader.importlib, "reload", fake_reload)

    reloader.reload_package(pkg)

    # Child should only be reloaded once
    assert reloaded.count(f"{base_dir}child.py") == 1
    # Package itself should be reloaded
    assert f"{base_dir}__init__.py" in reloaded
