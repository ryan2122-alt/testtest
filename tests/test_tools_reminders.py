from unittest.mock import MagicMock, patch

from jarvis.tools.reminders import _escape_applescript, create_reminder

MALICIOUS_TITLE = '"; do shell script "rm -rf ~"; --'


def test_escape_applescript_handles_quotes_and_backslashes():
    assert _escape_applescript('say "hi"') == 'say \\"hi\\"'
    assert _escape_applescript("back\\slash") == "back\\\\slash"


@patch("jarvis.tools.reminders.subprocess.run")
def test_create_reminder_builds_expected_script(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stderr="")

    result = create_reminder(title="Buy milk", list_name="Reminders")

    assert result.ok
    script = mock_run.call_args[0][0][2]
    assert 'name:"Buy milk"' in script
    assert 'tell list "Reminders"' in script


@patch("jarvis.tools.reminders.subprocess.run")
def test_create_reminder_escapes_malicious_title(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stderr="")

    create_reminder(title=MALICIOUS_TITLE)

    script = mock_run.call_args[0][0][2]
    # Every quote in the title must be backslash-escaped before landing
    # inside the AppleScript string literal, so it can't terminate the
    # literal early and inject additional AppleScript commands.
    assert f'name:"{_escape_applescript(MALICIOUS_TITLE)}"' in script


def test_create_reminder_invalid_due_date_reports_failure():
    result = create_reminder(title="X", due_date="not-a-date")
    assert not result.ok
    assert "Invalid due_date" in result.content
