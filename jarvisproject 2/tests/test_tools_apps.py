from unittest.mock import MagicMock, patch

import pytest

from jarvis.tools.apps import open_app, quit_app


@patch("jarvis.tools.apps.subprocess.run")
def test_open_app_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stderr="")

    result = open_app("Safari")

    assert result.ok
    mock_run.assert_called_once_with(
        ["open", "-a", "Safari"], capture_output=True, text=True, timeout=10
    )


@patch("jarvis.tools.apps.subprocess.run")
def test_quit_app_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stderr="")

    result = quit_app("Notes")

    assert result.ok
    args = mock_run.call_args[0][0]
    assert args[0] == "osascript"
    assert 'tell application "Notes" to quit' in args[2]


@patch("jarvis.tools.apps.subprocess.run")
def test_open_app_failure_reported(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stderr="not found")

    result = open_app("NoSuchApp")

    assert not result.ok
    assert "not found" in result.content


@pytest.mark.parametrize(
    "malicious_name",
    [
        'Safari"; do shell script "rm -rf ~"; tell application "Safari',
        "Notes\ndo shell script \"echo pwned\"",
        "App`touch /tmp/pwned`",
    ],
)
def test_app_name_injection_is_rejected(malicious_name):
    result = open_app(malicious_name)
    assert not result.ok
    assert "disallowed characters" in result.content


def test_open_app_never_shells_out_with_shell_true():
    # Guard against a future regression reintroducing shell=True, which
    # combined with a validated-but-imperfect name filter could still be risky.
    import inspect

    from jarvis.tools import apps

    source = inspect.getsource(apps)
    assert "shell=True" not in source
