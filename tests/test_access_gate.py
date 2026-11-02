import io
import json
import urllib.request
import urllib.error
import pytest
from app.utils import access_gate
from app.utils.access_gate import (
    is_machine_whitelisted,
    whitelist_current_machine,
    get_machine_fingerprint,
    get_short_node_id,
    get_telegram_credentials,
    save_telegram_credentials,
    send_telegram_access_request,
    check_telegram_approval,
)


class MockHTTPResponse:
    """Mock context manager response for urllib.request.urlopen."""
    def __init__(self, data_dict: dict, status: int = 200):
        self._data = json.dumps(data_dict).encode("utf-8")
        self.status = status

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# =========================================================================
# Whitelist & Cryptographic Licensing Tests
# =========================================================================

def test_is_machine_whitelisted_missing_file():
    """Verify is_machine_whitelisted returns False when license file is absent."""
    if access_gate.WHITELIST_FILE.exists():
        access_gate.WHITELIST_FILE.unlink()
    assert is_machine_whitelisted() is False


def test_is_machine_whitelisted_corrupted_json():
    """Verify is_machine_whitelisted handles corrupted/invalid JSON gracefully."""
    access_gate.WHITELIST_FILE.write_text("{corrupt: json: data", encoding="utf-8")
    assert is_machine_whitelisted() is False


def test_is_machine_whitelisted_missing_signature():
    """Verify is_machine_whitelisted returns False when signature key is missing."""
    access_gate.WHITELIST_FILE.write_text(json.dumps({"node_id": "NODE-1234"}), encoding="utf-8")
    assert is_machine_whitelisted() is False


def test_is_machine_whitelisted_forged_signature():
    """Verify forged/invalid HMAC signature fails verification."""
    data = {
        "node_id": "NODE-FAKE",
        "signature": "deadbeefcafebabe1234567890abcdef0123456789abcdef0123456789abcdef",
        "pin": "0000"
    }
    access_gate.WHITELIST_FILE.write_text(json.dumps(data), encoding="utf-8")
    assert is_machine_whitelisted() is False


def test_whitelist_current_machine_lifecycle():
    """Verify whitelist_current_machine generates a valid signature that verifies."""
    if access_gate.WHITELIST_FILE.exists():
        access_gate.WHITELIST_FILE.unlink()

    assert is_machine_whitelisted() is False

    success = whitelist_current_machine(approved_pin="8492")
    assert success is True
    assert access_gate.WHITELIST_FILE.exists() is True

    # Now verification must pass
    assert is_machine_whitelisted() is True

    # Check license file content
    lic_data = json.loads(access_gate.WHITELIST_FILE.read_text(encoding="utf-8"))
    assert lic_data.get("pin") == "8492"
    assert "signature" in lic_data
    assert lic_data.get("node_id") == get_short_node_id()


def test_get_short_node_id_format():
    """Verify node ID has format NODE-XXXXXX."""
    node_id = get_short_node_id()
    assert isinstance(node_id, str)
    assert node_id.startswith("NODE-")
    assert len(node_id) == 11


# =========================================================================
# Telegram Credentials Tests
# =========================================================================

def test_telegram_credentials_persistence(monkeypatch):
    """Verify saving and retrieving Telegram credentials via local config."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    saved = save_telegram_credentials("test_token_123", "chat_999")
    assert saved is True
    assert access_gate.TELEGRAM_CONFIG_FILE.exists()

    bot_token, chat_id = get_telegram_credentials()
    assert bot_token == "test_token_123"
    assert chat_id == "chat_999"


# =========================================================================
# Telegram API Request & Approval Tests (Mocked Network)
# =========================================================================

def test_send_telegram_access_request_parameter_flexibility(monkeypatch):
    """
    R1 Contract: send_telegram_access_request must accept node_id as single arg
    or keyword arg, and default credentials when omitted, without raising TypeError.
    """
    mock_resp = MockHTTPResponse({"ok": True, "result": {"message_id": 42}})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: mock_resp)

    # 1. No arguments
    ok, msg = send_telegram_access_request()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)

    # 2. Single positional argument (node_id)
    ok, msg = send_telegram_access_request("NODE-TEST1")
    assert isinstance(ok, bool)

    # 3. Keyword argument
    ok, msg = send_telegram_access_request(node_id="NODE-TEST2")
    assert isinstance(ok, bool)

    # 4. All arguments
    ok, msg = send_telegram_access_request("NODE-TEST3", "fake_token", "fake_chat")
    assert isinstance(ok, bool)


def test_send_telegram_access_request_mock_success(monkeypatch):
    """Verify successful dispatch message when Telegram API returns ok=True."""
    mock_resp = MockHTTPResponse({"ok": True, "result": {"message_id": 100}})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: mock_resp)

    ok, msg = send_telegram_access_request(
        node_id="NODE-ABCD",
        bot_token="valid_token",
        chat_id="valid_chat"
    )
    assert ok is True
    assert "dispatched" in msg.lower()


def test_send_telegram_access_request_mock_api_error(monkeypatch):
    """Verify handling when Telegram API returns ok=False with description."""
    mock_resp = MockHTTPResponse({"ok": False, "description": "Unauthorized bot token"})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: mock_resp)

    ok, msg = send_telegram_access_request(
        node_id="NODE-ABCD",
        bot_token="invalid_token",
        chat_id="valid_chat"
    )
    assert ok is False
    assert "Unauthorized bot token" in msg


def test_send_telegram_access_request_mock_network_exception(monkeypatch):
    """Verify network exception handling returns (False, msg) without crashing."""
    def raise_net_error(req, timeout=10):
        raise urllib.error.URLError("Network unreachable")

    monkeypatch.setattr(urllib.request, "urlopen", raise_net_error)

    ok, msg = send_telegram_access_request(
        node_id="NODE-ABCD",
        bot_token="token",
        chat_id="chat"
    )
    assert ok is False
    assert "Network unreachable" in msg or "Network error" in msg


def test_check_telegram_approval_parameter_flexibility(monkeypatch):
    """
    R1 Contract: check_telegram_approval must accept node_id as single arg
    or keyword arg, and default credentials when omitted, without raising TypeError.
    """
    mock_resp = MockHTTPResponse({"ok": True, "result": []})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: mock_resp)

    # 1. No arguments
    ok, val = check_telegram_approval()
    assert isinstance(ok, bool)
    assert isinstance(val, str)

    # 2. Single positional argument (node_id)
    ok, val = check_telegram_approval("NODE-TEST1")
    assert isinstance(ok, bool)

    # 3. Keyword argument
    ok, val = check_telegram_approval(node_id="NODE-TEST2")
    assert isinstance(ok, bool)

    # 4. All arguments
    ok, val = check_telegram_approval("NODE-TEST3", "fake_token", "fake_chat", "8492")
    assert isinstance(ok, bool)


def test_check_telegram_approval_mock_approved(monkeypatch):
    """Verify approval detection when admin replies /approve NODE-TEST 8492."""
    target_node = "NODE-BEEF"
    target_pin = "8492"
    chat_id = "8196296723"

    mock_resp = MockHTTPResponse({
        "ok": True,
        "result": [
            {
                "message": {
                    "chat": {"id": int(chat_id)},
                    "text": f"/approve {target_node} {target_pin}"
                }
            }
        ]
    })
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: mock_resp)

    # When polled without entered_pin from access_modal.py:
    # approved, pin = check_telegram_approval(self._node_id)
    approved, pin_result = check_telegram_approval(
        node_id=target_node,
        bot_token="test_token",
        chat_id=chat_id
    )
    assert approved is True
    # Should return target_pin or success indication matching target_pin
    assert target_pin in pin_result or pin_result == target_pin

    # When verified with entered_pin
    approved, msg = check_telegram_approval(
        node_id=target_node,
        bot_token="test_token",
        chat_id=chat_id,
        entered_pin=target_pin
    )
    assert approved is True
    assert is_machine_whitelisted() is True


def test_check_telegram_approval_mock_pin_mismatch(monkeypatch):
    """Verify entered_pin mismatch returns False."""
    target_node = "NODE-BEEF"
    chat_id = "8196296723"

    mock_resp = MockHTTPResponse({
        "ok": True,
        "result": [
            {
                "message": {
                    "chat": {"id": int(chat_id)},
                    "text": f"/approve {target_node} 8492"
                }
            }
        ]
    })
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: mock_resp)

    approved, msg = check_telegram_approval(
        node_id=target_node,
        bot_token="test_token",
        chat_id=chat_id,
        entered_pin="9999"  # Wrong PIN
    )
    assert approved is False
    assert "does not match" in msg.lower() or "not match" in msg.lower()


def test_check_telegram_approval_mock_waiting(monkeypatch):
    """Verify waiting message when no matching approval is in updates."""
    mock_resp = MockHTTPResponse({"ok": True, "result": []})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: mock_resp)

    approved, msg = check_telegram_approval(
        node_id="NODE-NONE",
        bot_token="test_token",
        chat_id="8196296723"
    )
    assert approved is False
    assert "waiting" in msg.lower() or "no approval" in msg.lower()
