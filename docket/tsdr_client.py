"""USPTO TSDR API client used by DocketTrack trademark imports.

The TSDR service allows at most 60 requests in a 60 second window for this
workflow.  The limiter below is shared by all worker threads so concurrency
cannot bypass that limit.
"""

from __future__ import annotations

import re
import threading
import time
import xml.etree.ElementTree as ET
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests


class SlidingWindowRateLimiter:
    """Thread-safe fixed-window limiter with no burst above the quota."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max(1, int(max_requests))
        self.window_seconds = max(1, int(window_seconds))
        self._request_times: deque[float] = deque()
        self._condition = threading.Condition()

    def acquire(self) -> None:
        """Block until one request is available in the current window."""
        while True:
            with self._condition:
                now = time.monotonic()
                cutoff = now - self.window_seconds
                while self._request_times and self._request_times[0] <= cutoff:
                    self._request_times.popleft()

                if len(self._request_times) < self.max_requests:
                    self._request_times.append(now)
                    return

                wait_for = max(0.01, self._request_times[0] + self.window_seconds - now)
                self._condition.wait(timeout=wait_for)


class TSDRAPIClient:
    """Fetch and parse one or more trademark records from TSDR."""

    def __init__(
        self,
        api_key: str,
        *,
        save_xml: bool = False,
        xml_output_dir: str | Path = "received_xml",
        max_requests: int = 60,
        window_seconds: int = 60,
        timeout: int = 15,
        max_retries: int = 3,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.base_url = "https://tsdrapi.uspto.gov"
        self.headers = {
            "USPTO-API-KEY": self.api_key,
            "Accept": "application/xml",
        }
        self.rate_limiter = SlidingWindowRateLimiter(max_requests, window_seconds)
        self.timeout = max(1, int(timeout))
        self.max_retries = max(0, int(max_retries))
        self.save_xml = bool(save_xml)
        self.xml_output_dir = Path(xml_output_dir)
        if self.save_xml:
            (self.xml_output_dir / "success").mkdir(parents=True, exist_ok=True)
            (self.xml_output_dir / "error").mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].split(":")[-1]

    @classmethod
    def _values(cls, root: ET.Element, name: str) -> list[str]:
        values = []
        for element in root.iter():
            if cls._local_name(element.tag) == name and element.text:
                value = " ".join(element.text.split())
                if value:
                    values.append(value)
        return values

    @classmethod
    def _first(cls, root: ET.Element, *names: str) -> str:
        for name in names:
            values = cls._values(root, name)
            if values:
                return values[0]
        return ""

    @staticmethod
    def _clean_xml_text(value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    @staticmethod
    def _format_p1_date(value: str) -> str:
        for fmt in ("%Y-%m-%d", "%Y%m%d", "%m-%d-%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).strftime("%m-%d-%Y")
            except (TypeError, ValueError):
                continue
        return value.strip() if value else ""

    @classmethod
    def extract_trademark_data(cls, xml_content: str) -> dict[str, Any]:
        """Extract the fields used by the dashboard from an XML response."""
        data: dict[str, Any] = {
            "mark_name": "",
            "serial_number": "",
            "filing_date": "",
            "status": "",
            "status_date": "",
            "registration_date": "",
            "owner_name": "",
            "owner_address": "",
            "class_numbers": [],
            "goods_services": "",
            "attorney_name": "",
            "correspondence_email": "",
            "contact_info": "",
            "prosecution_history": "",
            "P1_date": "",
        }
        if not xml_content:
            return data

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as exc:
            raise ValueError(f"TSDR returned invalid XML: {exc}") from exc

        data["mark_name"] = cls._first(root, "MarkVerbalElementText")
        data["serial_number"] = cls._first(root, "ApplicationNumberText")
        data["filing_date"] = cls._first(root, "ApplicationDate")
        data["status"] = cls._first(root, "MarkCurrentStatusExternalDescriptionText")
        data["status_date"] = cls._first(root, "MarkCurrentStatusDate")
        data["registration_date"] = cls._first(root, "RegistrationDate")
        data["owner_name"] = cls._first(root, "PersonFullName", "LegalEntityName")
        data["owner_address"] = ", ".join(cls._values(root, "AddressLineText"))
        data["class_numbers"] = list(dict.fromkeys(cls._values(root, "ClassNumber")))

        goods = cls._first(root, "GoodsServicesDescriptionText")
        data["goods_services"] = goods[:500] + "…" if len(goods) > 500 else goods
        data["attorney_name"] = cls._first(root, "RecordAttorneyPersonFullName", "AttorneyName")
        data["correspondence_email"] = ", ".join(dict.fromkeys(cls._values(root, "EmailAddressText")))
        data["contact_info"] = " | ".join(dict.fromkeys(cls._values(root, "PhoneNumber")))
        data["prosecution_history"] = cls._first(root, "MarkEventDescriptionText")
        data["P1_date"] = cls._format_p1_date(cls._first(root, "MarkEventDate"))
        return data

    def save_xml_to_file(self, serial_number: str, xml_content: str, success: bool) -> str | None:
        if not self.save_xml or not xml_content:
            return None
        folder = self.xml_output_dir / ("success" if success else "error")
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"sn{serial_number}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}.xml"
        path = folder / filename
        try:
            root = ET.fromstring(xml_content)
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        except (ET.ParseError, OSError):
            try:
                path.write_text(xml_content, encoding="utf-8")
            except OSError:
                return None
        return str(path)

    def get_trademark_details(self, serial_number: str) -> dict[str, Any]:
        """Fetch one serial number with retry and quota-aware error handling."""
        serial = re.sub(r"\D", "", str(serial_number or ""))
        result: dict[str, Any] = {
            "serial_number": serial,
            "status_code": None,
            "success": False,
            "error": None,
            "data": {},
            "xml_content": None,
        }
        if not serial:
            result["error"] = "Serial number is empty"
            return result
        if not self.api_key:
            result["error"] = "USPTO TSDR API key is not configured"
            return result

        url = f"{self.base_url}/ts/cd/casestatus/sn{serial}/info.xml"
        for attempt in range(self.max_retries + 1):
            self.rate_limiter.acquire()
            try:
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
            except requests.RequestException as exc:
                result["error"] = f"Network error: {exc}"
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                return result

            result["status_code"] = response.status_code
            result["xml_content"] = response.text
            if response.status_code == 200:
                try:
                    result["data"] = self.extract_trademark_data(response.text)
                    result["success"] = True
                    self.save_xml_to_file(serial, response.text, success=True)
                except (ValueError, ET.ParseError) as exc:
                    result["error"] = str(exc)
                    self.save_xml_to_file(serial, response.text, success=False)
                return result

            if response.status_code == 404:
                result["error"] = "Trademark serial number was not found"
                self.save_xml_to_file(serial, response.text, success=False)
                return result

            result["error"] = f"USPTO TSDR returned HTTP {response.status_code}"
            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After")
                try:
                    wait_for = float(retry_after) if retry_after else min(2 ** attempt, 30)
                except ValueError:
                    wait_for = min(2 ** attempt, 30)
                time.sleep(max(0.1, wait_for))
                continue
            self.save_xml_to_file(serial, response.text, success=False)
            return result

        return result

    def fetch_many(self, serial_numbers: list[str], max_workers: int = 10) -> list[dict[str, Any]]:
        """Fetch a batch concurrently while sharing the 60-per-60s limiter."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        unique_serials = list(dict.fromkeys(re.sub(r"\D", "", str(value or "")) for value in serial_numbers))
        unique_serials = [value for value in unique_serials if value]
        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max(1, min(int(max_workers), 10))) as executor:
            future_map = {executor.submit(self.get_trademark_details, serial): serial for serial in unique_serials}
            for future in as_completed(future_map):
                serial = future_map[future]
                try:
                    results.append(future.result())
                except Exception as exc:  # defensive: one record must not stop a batch
                    results.append({
                        "serial_number": serial,
                        "status_code": None,
                        "success": False,
                        "error": f"Unexpected worker error: {exc}",
                        "data": {},
                        "xml_content": None,
                    })
        return results
