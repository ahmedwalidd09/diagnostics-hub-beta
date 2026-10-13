import time
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

try:
    import wmi
    import pythoncom
except ImportError:
    wmi = None
    pythoncom = None

_cached_cpu_temp: Optional[float] = None
_last_cpu_temp_time = 0.0
_cpu_temp_backoff_until = 0.0


def get_cpu_temperature() -> Optional[float]:
    """
    Attempt to read CPU temperature via OpenHardwareMonitor WMI namespace,
    falling back to ACPI ThermalZone in root\\wmi.
    Returns temperature in degrees Celsius, or None if unavailable.
    Caches successful readings for 10s and backs off 30s on failure to prevent COM RPC overhead.
    """
    global _cached_cpu_temp, _last_cpu_temp_time, _cpu_temp_backoff_until
    if not wmi:
        return None

    now = time.time()
    if now < _cpu_temp_backoff_until:
        return _cached_cpu_temp

    if _cached_cpu_temp is not None and (now - _last_cpu_temp_time < 10.0):
        return _cached_cpu_temp

    com_initialized = False
    temp_found: Optional[float] = None
    try:
        if pythoncom:
            pythoncom.CoInitialize()
            com_initialized = True

        # Method 1: OpenHardwareMonitor
        try:
            ohm = wmi.WMI(namespace=r"root\OpenHardwareMonitor")
            sensors = ohm.Sensor()
            cpu_temps = []
            for sensor in sensors:
                if getattr(sensor, "SensorType", "") == "Temperature" and "cpu" in str(getattr(sensor, "Name", "")).lower():
                    val = getattr(sensor, "Value", None)
                    if val is not None:
                        cpu_temps.append(float(val))
            if cpu_temps:
                temp_found = round(sum(cpu_temps) / len(cpu_temps), 1)
        except Exception:
            pass

        # Method 2: MSAcpi_ThermalZoneTemperature in root\wmi
        if temp_found is None:
            try:
                wmi_acpi = wmi.WMI(namespace=r"root\wmi")
                zones = wmi_acpi.MSAcpi_ThermalZoneTemperature()
                for zone in zones:
                    kelvin_tenths = getattr(zone, "CurrentTemperature", None)
                    if kelvin_tenths:
                        celsius = (float(kelvin_tenths) / 10.0) - 273.15
                        if 0 < celsius < 125:
                            temp_found = round(celsius, 1)
                            break
            except Exception:
                pass

    except Exception as e:
        logger.debug(f"Failed to query CPU temperature via WMI: {e}")

    if temp_found is not None:
        _cached_cpu_temp = temp_found
        _last_cpu_temp_time = now
    else:
        # Back off for 30s to prevent stalling the worker with failed WMI connections
        _cpu_temp_backoff_until = now + 30.0

    return temp_found


def get_disk_media_types() -> Dict[str, str]:
    """
    Determine if physical disks are SSD or HDD.
    Returns mapping of disk DeviceID/Caption to MediaType string ('SSD', 'HDD', or 'Unknown').
    """
    media_types = {}
    if not wmi:
        return media_types

    com_initialized = False
    try:
        if pythoncom:
            pythoncom.CoInitialize()
            com_initialized = True

        # Query Microsoft Storage namespace for MediaType (3=HDD, 4=SSD, 5=SCM)
        try:
            storage_wmi = wmi.WMI(namespace=r"root\Microsoft\Windows\Storage")
            physical_disks = storage_wmi.MSFT_PhysicalDisk()
            for disk in physical_disks:
                device_id = getattr(disk, "DeviceId", "")
                disk_type_val = getattr(disk, "MediaType", 0)
                model = getattr(disk, "FriendlyName", f"Disk {device_id}")
                if disk_type_val == 4:
                    media_types[model] = "SSD"
                elif disk_type_val == 3:
                    media_types[model] = "HDD"
                else:
                    media_types[model] = "SSD" if "ssd" in model.lower() or "nvme" in model.lower() else "Unknown"
            if media_types:
                return media_types
        except Exception:
            pass

        # Fallback to standard Win32_DiskDrive
        try:
            c = wmi.WMI()
            for drive in c.Win32_DiskDrive():
                caption = getattr(drive, "Caption", "Disk")
                raw_type = getattr(drive, "MediaType", "")
                if "solid state" in str(raw_type).lower() or "ssd" in str(caption).lower() or "nvme" in str(caption).lower():
                    media_types[caption] = "SSD"
                elif "hard disk" in str(raw_type).lower() or "fixed" in str(raw_type).lower():
                    media_types[caption] = "HDD"
                else:
                    media_types[caption] = "Unknown"
        except Exception:
            pass

    except Exception as e:
        logger.debug(f"Error querying disk types: {e}")

    return media_types
