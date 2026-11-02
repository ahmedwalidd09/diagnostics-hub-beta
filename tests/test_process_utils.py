import subprocess
from unittest.mock import MagicMock
import psutil
import pytest
from app.utils.process_utils import kill_process_with_fallback


def test_kill_process_tier1_psutil_success(monkeypatch):
    """Verify Tier 1 psutil kills process directly without invoking taskkill."""
    mock_proc = MagicMock()
    monkeypatch.setattr(psutil, "Process", lambda pid: mock_proc)

    mock_run = MagicMock()
    monkeypatch.setattr(subprocess, "run", mock_run)

    success = kill_process_with_fallback(1234)

    assert success is True
    mock_proc.kill.assert_called_once()
    mock_run.assert_not_called()


def test_kill_process_tier1_tree_recursion(monkeypatch):
    """Verify tree=True recursively terminates child processes before parent."""
    mock_child1 = MagicMock()
    mock_child2 = MagicMock()
    mock_proc = MagicMock()
    mock_proc.children.return_value = [mock_child1, mock_child2]

    monkeypatch.setattr(psutil, "Process", lambda pid: mock_proc)

    mock_run = MagicMock()
    monkeypatch.setattr(subprocess, "run", mock_run)

    success = kill_process_with_fallback(1234, tree=True)

    assert success is True
    mock_proc.children.assert_called_once_with(recursive=True)
    mock_child1.kill.assert_called_once()
    mock_child2.kill.assert_called_once()
    mock_proc.kill.assert_called_once()
    mock_run.assert_not_called()


def test_kill_process_tier1_child_kill_exception_resilience(monkeypatch):
    """Verify exceptions during child kill do not prevent parent termination."""
    mock_child = MagicMock()
    mock_child.kill.side_effect = psutil.NoSuchProcess(pid=9999)
    mock_proc = MagicMock()
    mock_proc.children.return_value = [mock_child]

    monkeypatch.setattr(psutil, "Process", lambda pid: mock_proc)

    success = kill_process_with_fallback(1234, tree=True)

    assert success is True
    mock_proc.kill.assert_called_once()


def test_kill_process_pid_type_conversion(monkeypatch):
    """Verify string PID representation is cleanly converted to integer."""
    captured_pids = []

    def mock_process(pid):
        captured_pids.append(pid)
        m = MagicMock()
        return m

    monkeypatch.setattr(psutil, "Process", mock_process)

    assert kill_process_with_fallback("4321") is True
    assert captured_pids == [4321]
    assert isinstance(captured_pids[0], int)


def test_kill_process_invalid_pid():
    """Verify invalid/unparseable PIDs return False without raising exceptions."""
    assert kill_process_with_fallback("not_a_number") is False
    assert kill_process_with_fallback(None) is False
    assert kill_process_with_fallback("") is False


def test_kill_process_tier2_taskkill_fallback(monkeypatch):
    """Verify Tier 2 taskkill fallback is executed if psutil fails."""
    def raise_psutil_error(pid):
        raise psutil.AccessDenied(pid=pid)

    monkeypatch.setattr(psutil, "Process", raise_psutil_error)

    captured_cmds = []

    def mock_subprocess_run(cmd, shell=True, capture_output=True, text=True):
        captured_cmds.append(cmd)
        res = MagicMock()
        res.returncode = 0
        return res

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    success = kill_process_with_fallback(5678)

    assert success is True
    assert len(captured_cmds) == 1
    assert "taskkill /F /PID 5678" in captured_cmds[0]
    assert "/T" not in captured_cmds[0]


def test_kill_process_tier2_taskkill_tree_flag(monkeypatch):
    """Verify Tier 2 taskkill includes /T flag when tree=True."""
    monkeypatch.setattr(psutil, "Process", MagicMock(side_effect=Exception("psutil error")))

    captured_cmds = []

    def mock_subprocess_run(cmd, shell=True, capture_output=True, text=True):
        captured_cmds.append(cmd)
        res = MagicMock()
        res.returncode = 0
        return res

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    success = kill_process_with_fallback(5678, tree=True)

    assert success is True
    assert len(captured_cmds) == 1
    assert captured_cmds[0] == "taskkill /F /PID 5678 /T"


def test_kill_process_both_tiers_fail(monkeypatch):
    """Verify False is returned when both psutil and taskkill fail."""
    monkeypatch.setattr(psutil, "Process", MagicMock(side_effect=Exception("psutil error")))

    mock_res = MagicMock()
    mock_res.returncode = 128  # Taskkill failed (process not found or access denied)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_res)

    success = kill_process_with_fallback(9999)
    assert success is False


def test_kill_process_taskkill_exception_handling(monkeypatch):
    """Verify subprocess exceptions are caught cleanly, returning False."""
    monkeypatch.setattr(psutil, "Process", MagicMock(side_effect=Exception("psutil error")))

    def raise_subproc_error(*args, **kwargs):
        raise OSError("Subprocess invocation failed")

    monkeypatch.setattr(subprocess, "run", raise_subproc_error)

    success = kill_process_with_fallback(9999)
    assert success is False
