import time
import requests
import logging
from typing import Optional, Dict, Any
from app.constants import VT_API_BASE

logger = logging.getLogger(__name__)


class VirusTotalClient:
    """VirusTotal v3 API Client with rate limiting (4 requests/minute)."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key.strip()
        self._last_request_time = 0.0
        self._min_interval = 15.1  # 4 requests per 60 seconds

    def set_api_key(self, api_key: str):
        self.api_key = api_key.strip()

    def _wait_for_rate_limit(self):
        """Enforce 15-second delay between requests for VT free tier."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def test_connection(self) -> Dict[str, Any]:
        """Test whether the provided API key is valid."""
        if not self.api_key:
            return {"valid": False, "message": "API key cannot be empty."}
        try:
            url = f"{VT_API_BASE}/users/current"
            headers = {"x-apikey": self.api_key, "accept": "application/json"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                user_id = data.get("data", {}).get("id", "Active")
                return {"valid": True, "message": f"Connected as {user_id}."}
            elif resp.status_code == 401 or resp.status_code == 403:
                return {"valid": False, "message": "Invalid API key or access denied."}
            else:
                return {"valid": False, "message": f"VirusTotal returned HTTP {resp.status_code}."}
        except Exception as e:
            return {"valid": False, "message": f"Connection error: {e}"}

    def check_file_hash(self, sha256_hash: str) -> Optional[Dict[str, Any]]:
        """
        Query VirusTotal for a file hash.
        Returns analysis stats or None if not found/error.
        """
        if not self.api_key or not sha256_hash:
            return None

        self._wait_for_rate_limit()

        try:
            url = f"{VT_API_BASE}/files/{sha256_hash}"
            headers = {"x-apikey": self.api_key, "accept": "application/json"}
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                body = resp.json()
                attrs = body.get("data", {}).get("attributes", {})
                stats = attrs.get("last_analysis_stats", {})
                return {
                    "malicious": stats.get("malicious", 0),
                    "suspicious": stats.get("suspicious", 0),
                    "harmless": stats.get("harmless", 0),
                    "undetected": stats.get("undetected", 0),
                    "meaningful_name": attrs.get("meaningful_name", ""),
                    "reputation": attrs.get("reputation", 0)
                }
            elif resp.status_code == 404:
                return {
                    "malicious": 0,
                    "suspicious": 0,
                    "harmless": 0,
                    "undetected": 0,
                    "message": "File hash not found in VirusTotal database"
                }
            else:
                logger.warning(f"VirusTotal query error HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Error connecting to VirusTotal: {e}")

        return None
