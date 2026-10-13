import os
import re
import json
import ctypes
from ctypes import wintypes
from pathlib import Path
import hashlib
import logging
from typing import Dict, Any, Optional
from app.constants import KNOWN_THREATS_PATH

logger = logging.getLogger(__name__)

# Known critical Windows binaries that must strictly run from System32/SysWOW64
SYSTEM_BINARIES = {
    "csrss.exe",
    "lsass.exe",
    "services.exe",
    "smss.exe",
    "wininit.exe",
    "winlogon.exe",
    "lsm.exe"
}

RANDOM_FOLDER_REGEX = re.compile(r"^[0-9a-fA-F]{8,}$|^[a-zA-Z0-9]{12,}$")


class ThreatSignatures:
    """Provides file hash, signature, and heuristic malware analysis."""

    def __init__(self, json_path=KNOWN_THREATS_PATH):
        self.json_path = json_path
        self.names = set()
        self.hashes = {}
        self.suspicious_ips = set()
        self.load()

    def load(self):
        try:
            if os.path.exists(self.json_path):
                with open(self.json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.names = set(str(n).lower() for n in data.get("names", []))
                    self.hashes = {str(k).lower(): str(v) for k, v in data.get("hashes", {}).items()}
                    self.suspicious_ips = set(str(ip) for ip in data.get("suspicious_ips", []))
        except Exception as e:
            logger.error(f"Failed to load known threat signatures: {e}")

    def is_known_threat_name(self, name: str) -> bool:
        return str(name).lower() in self.names

    def is_known_threat_hash(self, file_hash: str) -> Optional[str]:
        return self.hashes.get(str(file_hash).lower())

    def is_suspicious_ip(self, ip: str) -> bool:
        return ip in self.suspicious_ips

    @staticmethod
    def calculate_file_sha256(file_path: str) -> Optional[str]:
        """Compute SHA-256 hash in 64KB chunks safely."""
        if not os.path.isfile(file_path):
            return None
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    sha256.update(chunk)
            return sha256.hexdigest().lower()
        except Exception:
            return None

    @staticmethod
    def is_suspicious_path(exe_path: str) -> bool:
        """Check if executable resides in temp folders or randomized directories."""
        if not exe_path:
            return False
        normalized = exe_path.replace("/", "\\").lower()
        # Temp directories check
        temp_paths = [
            os.environ.get("TEMP", "").lower(),
            os.environ.get("TMP", "").lower(),
            r"\appdata\local\temp",
            r"\windows\temp"
        ]
        for t in temp_paths:
            if t and t in normalized:
                return True

        # Check directory names for random hex/entropy
        parts = Path(exe_path).parts
        for part in parts[:-1]:
            if RANDOM_FOLDER_REGEX.match(part):
                return True
        return False

    @staticmethod
    def is_system_duplicate_impostor(process_name: str, exe_path: str) -> bool:
        """Flag critical system names running outside System32/SysWOW64."""
        name_lower = str(process_name).lower()
        if name_lower in SYSTEM_BINARIES:
            if not exe_path:
                return True
            path_lower = exe_path.replace("/", "\\").lower()
            if "\\windows\\system32\\" not in path_lower and "\\windows\\syswow64\\" not in path_lower:
                return True
        return False

    @staticmethod
    def verify_digital_signature(file_path: str) -> bool:
        """
        Verify Authenticode digital signature via WinVerifyTrust.
        Returns True if signed and trusted, False if unsigned or failed.
        """
        if not os.path.exists(file_path):
            return False

        try:
            class WINTRUST_FILE_INFO(ctypes.Structure):
                _fields_ = [
                    ("cbStruct", wintypes.DWORD),
                    ("pcwszFilePath", wintypes.LPCWSTR),
                    ("hFile", wintypes.HANDLE),
                    ("pgKnownSubject", ctypes.c_void_p),
                ]

            class WINTRUST_DATA(ctypes.Structure):
                _fields_ = [
                    ("cbStruct", wintypes.DWORD),
                    ("pPolicyCallbackData", ctypes.c_void_p),
                    ("pSIPClientData", ctypes.c_void_p),
                    ("dwUIChoice", wintypes.DWORD),
                    ("fdwRevocationChecks", wintypes.DWORD),
                    ("dwUnionChoice", wintypes.DWORD),
                    ("pFile", ctypes.POINTER(WINTRUST_FILE_INFO)),
                    ("dwStateAction", wintypes.DWORD),
                    ("hWVTStateData", wintypes.HANDLE),
                    ("pwszURLReference", wintypes.LPCWSTR),
                    ("dwProvFlags", wintypes.DWORD),
                    ("dwUIContext", wintypes.DWORD),
                    ("pSignatureSettings", ctypes.c_void_p),
                ]

            WTD_UI_NONE = 2
            WTD_REVOKE_NONE = 0
            WTD_CHOICE_FILE = 1
            WTD_STATEACTION_IGNORE = 0
            WTD_SAFER_FLAG = 0x00000100

            file_info = WINTRUST_FILE_INFO()
            file_info.cbStruct = ctypes.sizeof(WINTRUST_FILE_INFO)
            file_info.pcwszFilePath = file_path
            file_info.hFile = None
            file_info.pgKnownSubject = None

            win_data = WINTRUST_DATA()
            win_data.cbStruct = ctypes.sizeof(WINTRUST_DATA)
            win_data.dwUIChoice = WTD_UI_NONE
            win_data.fdwRevocationChecks = WTD_REVOKE_NONE
            win_data.dwUnionChoice = WTD_CHOICE_FILE
            win_data.pFile = ctypes.pointer(file_info)
            win_data.dwStateAction = WTD_STATEACTION_IGNORE
            win_data.dwProvFlags = WTD_SAFER_FLAG

            # WINTRUST_ACTION_GENERIC_VERIFY_V2 GUID
            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            action_guid = GUID(
                0x00AAC56B,
                0xCD44,
                0x11D0,
                (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE)
            )

            wintrust = ctypes.windll.wintrust
            l_status = wintrust.WinVerifyTrust(
                None,
                ctypes.byref(action_guid),
                ctypes.byref(win_data)
            )
            # ERROR_SUCCESS is 0
            return l_status == 0
        except Exception:
            return False


# Singleton instance
threat_db = ThreatSignatures()
