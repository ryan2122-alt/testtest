from unittest.mock import MagicMock, patch

from jarvis.tools.system import set_brightness, set_volume, shutdown_mac


@patch("jarvis.tools.system.subprocess.run")
def test_set_volume_clamps_to_0_100(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stderr="")

    set_volume(150)
    script = mock_run.call_args[0][0][2]
    assert "output volume 100" in script

    set_volume(-20)
    script = mock_run.call_args[0][0][2]
    assert "output volume 0" in script


@patch("jarvis.tools.system.subprocess.run")
def test_set_brightness_clamps_and_scales(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stderr="")

    set_brightness(50)
    script = mock_run.call_args[0][0][2]
    assert "brightness of first display to 0.5" in script


@patch("jarvis.tools.system.subprocess.run")
def test_shutdown_mac_uses_fixed_no_argument_script(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stderr="")

    result = shutdown_mac()

    assert result.ok
    call_args = mock_run.call_args[0][0]
    assert call_args == ["osascript", "-e", 'tell application "System Events" to shut down']
