import datetime
from types import SimpleNamespace

import pytest
import pytz

from TDTbot import git_manage


class FakeRemote:
    def __init__(self, result):
        self.result = result
        self.called = False

    def pull(self):
        self.called = True
        return self.result


class FakeRepo:
    def __init__(self, remote_result=None, commits=None, head_commit=None):
        self._remote_result = remote_result
        self._commits = commits or []
        self.head = SimpleNamespace(commit=head_commit)

    def remote(self):
        return FakeRemote(self._remote_result)

    def iter_commits(self):
        return self._commits


def test_update_returns_none_when_repo_missing():
    assert git_manage.update(repo=None) is None


def test_update_calls_remote_pull_and_returns_value():
    repo = FakeRepo(remote_result="pulled")
    assert git_manage.update(repo) == "pulled"


def test_git_log_items_returns_empty_without_repo():
    assert git_manage.git_log_items(repo=None) == []


def test_git_log_items_formats_commits(monkeypatch):
    now = pytz.utc.localize(datetime.datetime(2024, 1, 1, 12, 0, 0))
    commit_dt = now - datetime.timedelta(minutes=5)
    commit = SimpleNamespace(
        committed_datetime=commit_dt,
        message="fix: thing",
        author=SimpleNamespace(name="alice"),
        hexsha="abcdef123456",
    )

    repo = FakeRepo(commits=[commit])

    # Make naturaltime deterministic
    monkeypatch.setattr(
        git_manage,
        "humanize",
        SimpleNamespace(naturaltime=lambda delta: "5 minutes ago"),
    )

    # Ensure utcnow returns the fixed now
    class FixedDatetime(datetime.datetime):
        @classmethod
        def utcnow(cls):
            return now.replace(tzinfo=None)

    monkeypatch.setattr(git_manage.datetime, "datetime", FixedDatetime)

    out = git_manage.git_log_items(repo=repo, look_back=datetime.timedelta(hours=1))
    assert out == ["5 minutes ago: fix: thing <alice> [abcdef1]"]


def test_last_updated_none_without_repo():
    assert git_manage.last_updated(repo=None) is None


def test_last_updated_returns_head_commit_datetime():
    dt = datetime.datetime(2023, 12, 31, tzinfo=pytz.utc)
    repo = FakeRepo(head_commit=SimpleNamespace(committed_datetime=dt))
    assert git_manage.last_updated(repo) is dt
