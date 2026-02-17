"""
Misc utility functions
"""

import os
import platform
import sys
import time
from typing import Iterable, Union

from .debug_logs import *


def now():
    return int(time.time() * 1000)


def exit_system() -> None:
    """Exit the system."""
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)


def check_platform():
    """
    Check if the script is running on a cross platform

    Returns:
        bool: True if running on cross platform
    """
    if platform.system() == "Darwin":
        return "Darwin"
    elif platform.system() == "Linux":
        return "Linux"
    elif platform.system() == "Windows":
        return "Windows"
    else:
        raise Exception("Unsupported platform")


def check_valid_mac(mac_address: str) -> bool:
    """Check if mac address is valid

    Args:
        mac_address (str): Mac address

    Returns:
        bool: True if mac address is valid
    """
    if len(mac_address) != 17:
        return False
    if mac_address.count(":") != 5:
        return False
    return True


def check_valid_uuid(uuid: str) -> bool:
    """Check if uuid is valid

    Args:
        uuid (str): UUID
    """
    if len(uuid) != 36:
        return False
    if uuid.count("-") != 4:
        return False
    return True


def check_ble_address(address) -> bool:
    """Check if the BLE address is valid

    Args:
        address (str): The MAC address of the Guardian Earbuds

    Returns:
        bool: True if the address is valid, False otherwise

    Raises:
        ValueError: If the MAC address is not valid
    """
    if check_platform() == "Windows" or check_platform() == "Linux" and check_valid_mac(address):
        return True
    elif check_platform() == "Darwin" and check_valid_uuid(address):
        logger.info("Platform detected: Darwin")
        return True
    else:
        logger.error("Invalid BLE address")
        raise ValueError("Invalid BLE address")


def compute_rolling_average(numbers: Iterable[Union[float, int]]) -> float:
    """
    Compute the rolling average of a list of numbers

    Args:
        numbers (Iterable[float]): List of numbers

    Returns:
        float: The rolling average of the list of numbers
    """
    return sum(numbers) / len(numbers) if numbers else 0.0
