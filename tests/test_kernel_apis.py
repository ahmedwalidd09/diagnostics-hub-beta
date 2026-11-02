import ctypes
from ctypes import wintypes
import pytest
from app.utils.ram_api import (
    get_kernel_performance_info,
    empty_all_working_sets,
    PERFORMANCE_INFORMATION,
)


def test_get_kernel_performance_info_live_execution():
    """Verify live Win32 GetPerformanceInfo returns valid metrics structure."""
    result = get_kernel_performance_info()

    assert isinstance(result, dict)
    expected_keys = {
        "kernel_paged_mb",
        "kernel_nonpaged_mb",
        "system_cache_mb",
        "commit_total_gb",
        "commit_limit_gb",
        "commit_percent",
        "nonpaged_warning",
        "handles",
        "threads",
        "processes",
    }
    assert expected_keys.issubset(result.keys())

    # Verify types
    assert isinstance(result["kernel_paged_mb"], float)
    assert isinstance(result["kernel_nonpaged_mb"], float)
    assert isinstance(result["system_cache_mb"], float)
    assert isinstance(result["commit_total_gb"], float)
    assert isinstance(result["commit_limit_gb"], float)
    assert isinstance(result["commit_percent"], float)
    assert isinstance(result["nonpaged_warning"], bool)
    assert isinstance(result["handles"], int)
    assert isinstance(result["threads"], int)
    assert isinstance(result["processes"], int)

    # On a live Windows system, metrics must be non-negative and realistic
    assert result["handles"] > 0
    assert result["processes"] > 0
    assert result["threads"] > 0
    assert result["commit_limit_gb"] > 0.0
    assert 0.0 <= result["commit_percent"] <= 100.0
    assert result["kernel_nonpaged_mb"] >= 0.0
    assert result["kernel_paged_mb"] >= 0.0
    assert result["nonpaged_warning"] == (result["kernel_nonpaged_mb"] > 800.0)


def test_get_kernel_performance_info_mock_warning_threshold_exceeded(monkeypatch):
    """Verify kernel_nonpaged_mb > 800 MB triggers nonpaged_warning=True."""
    page_size = 4096
    target_nonpaged_mb = 950.0
    target_commit_total_gb = 8.0
    target_commit_limit_gb = 16.0

    class MockPsapi:
        def GetPerformanceInfo(self, perf_info_ptr, cb):
            perf = getattr(perf_info_ptr, "_obj", perf_info_ptr)
            perf.PageSize = page_size
            perf.KernelNonpaged = int(target_nonpaged_mb * (1024 * 1024) / page_size)
            perf.KernelPaged = int(400.0 * (1024 * 1024) / page_size)
            perf.SystemCache = int(1200.0 * (1024 * 1024) / page_size)
            perf.CommitTotal = int(target_commit_total_gb * (1024 ** 3) / page_size)
            perf.CommitLimit = int(target_commit_limit_gb * (1024 ** 3) / page_size)
            perf.HandleCount = 12345
            perf.ThreadCount = 1500
            perf.ProcessCount = 120
            return 1

    monkeypatch.setattr(ctypes, "WinDLL", lambda name, use_last_error=True: MockPsapi())

    result = get_kernel_performance_info()
    assert result["kernel_nonpaged_mb"] == target_nonpaged_mb
    assert result["nonpaged_warning"] is True
    assert result["commit_total_gb"] == target_commit_total_gb
    assert result["commit_limit_gb"] == target_commit_limit_gb
    assert result["commit_percent"] == 50.0
    assert result["handles"] == 12345
    assert result["threads"] == 1500
    assert result["processes"] == 120


def test_get_kernel_performance_info_mock_warning_threshold_normal(monkeypatch):
    """Verify kernel_nonpaged_mb <= 800 MB sets nonpaged_warning=False."""
    page_size = 4096
    target_nonpaged_mb = 450.0

    class MockPsapi:
        def GetPerformanceInfo(self, perf_info_ptr, cb):
            perf = getattr(perf_info_ptr, "_obj", perf_info_ptr)
            perf.PageSize = page_size
            perf.KernelNonpaged = int(target_nonpaged_mb * (1024 * 1024) / page_size)
            perf.KernelPaged = int(300.0 * (1024 * 1024) / page_size)
            perf.SystemCache = int(800.0 * (1024 * 1024) / page_size)
            perf.CommitTotal = int(4.0 * (1024 ** 3) / page_size)
            perf.CommitLimit = int(16.0 * (1024 ** 3) / page_size)
            perf.HandleCount = 5000
            perf.ThreadCount = 800
            perf.ProcessCount = 70
            return 1

    monkeypatch.setattr(ctypes, "WinDLL", lambda name, use_last_error=True: MockPsapi())

    result = get_kernel_performance_info()
    assert result["kernel_nonpaged_mb"] == target_nonpaged_mb
    assert result["nonpaged_warning"] is False


def test_get_kernel_performance_info_mock_boundary_conditions(monkeypatch):
    """Verify exact 800.0 boundary does not trigger warning, but 800.1 does."""
    page_size = 4096

    def create_mock(nonpaged_mb):
        class MockPsapi:
            def GetPerformanceInfo(self, perf_info_ptr, cb):
                perf = getattr(perf_info_ptr, "_obj", perf_info_ptr)
                perf.PageSize = page_size
                perf.KernelNonpaged = int(nonpaged_mb * (1024 * 1024) / page_size)
                perf.KernelPaged = 1000
                perf.CommitTotal = 1000
                perf.CommitLimit = 2000
                return 1
        return MockPsapi()

    # At exactly 800.0 MB -> warning must be False
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, use_last_error=True: create_mock(800.0))
    res_800 = get_kernel_performance_info()
    assert res_800["kernel_nonpaged_mb"] == 800.0
    assert res_800["nonpaged_warning"] is False

    # At 800.1 MB -> warning must be True
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, use_last_error=True: create_mock(800.1))
    res_800_1 = get_kernel_performance_info()
    assert res_800_1["kernel_nonpaged_mb"] == 800.1
    assert res_800_1["nonpaged_warning"] is True


def test_get_kernel_performance_info_error_fallback_windll_exception(monkeypatch):
    """Verify WinDLL exception is caught and returns zeroed fallback dictionary."""
    def raise_error(name, use_last_error=True):
        raise OSError("DLL psapi not found in test environment")

    monkeypatch.setattr(ctypes, "WinDLL", raise_error)

    result = get_kernel_performance_info()
    assert result == {
        "kernel_paged_mb": 0.0,
        "kernel_nonpaged_mb": 0.0,
        "system_cache_mb": 0.0,
        "commit_total_gb": 0.0,
        "commit_limit_gb": 0.0,
        "commit_percent": 0.0,
        "nonpaged_warning": False,
        "handles": 0,
        "threads": 0,
        "processes": 0,
    }


def test_get_kernel_performance_info_error_fallback_api_call_fails(monkeypatch):
    """Verify when GetPerformanceInfo returns False (0), zeroed fallback is returned."""
    class MockPsapiFailing:
        def GetPerformanceInfo(self, perf_info_ptr, cb):
            return 0  # Win32 failure

    monkeypatch.setattr(ctypes, "WinDLL", lambda name, use_last_error=True: MockPsapiFailing())

    result = get_kernel_performance_info()
    assert result["commit_total_gb"] == 0.0
    assert result["nonpaged_warning"] is False
    assert result["handles"] == 0


def test_empty_all_working_sets():
    """Verify empty_all_working_sets executes and returns non-negative count."""
    count = empty_all_working_sets()
    assert isinstance(count, int)
    assert count >= 0
