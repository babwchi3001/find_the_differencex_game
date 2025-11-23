"""
Misc utility functions
"""

import platform
import time
from functools import wraps
from .debug_logs import *
import sys
import os
from .config import settings
import requests
import asyncio
from idun_data_models import RecordingStatusOut
import idun_data_models
import orjson, httpx


async def request(
    request_verb,
    base_url,
    deviceID,
    recordingApiPath,
    payload=None,
    params=None,
    password="",
):
    jsonPayload = None
    if payload is not None:
        if isinstance(payload, list):
            # We need to use the `orjson` library instead of the stdlib `json`
            # because it doesn't know how to handle datetime
            try:
                jsonPayload = orjson.dumps([p.dict() for p in payload])
            except AttributeError:
                jsonPayload = orjson.dumps(payload)
        else:
            try:
                jsonPayload = payload.json()
            except AttributeError:
                jsonPayload = orjson.dumps(payload)
    async with httpx.AsyncClient() as client:
        end_point_url = f"devices/{deviceID}/recordings{recordingApiPath}"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        response = await client.request(
            request_verb,
            base_url + end_point_url,
            headers=headers,
            data=jsonPayload,
            params=params,
            auth=(deviceID, password),
        )
    print("Response status", response.status_code)
    print("Details", response.content.decode())
    return response.content


def string_detail_to_log(details: str):
    i1 = details.find("{")
    i2 = details.find("}")
    message = details[i1 + 2 : i2 - 1]
    return message


def retry(debug, tries_numb=4, delay=2):
    def retry_decorator(f):
        @wraps(f)
        def retry_fun(*args, **kwargs):
            trials = 0
            while trials != tries_numb:
                try:
                    log_calling_function_while_retrying(debug, f"calling {f.__name__}")
                    return f(*args, **kwargs)

                except Exception as e:
                    if debug:
                        log_message_retry(debug, trials)
                    else:
                        print(f"Trials Number {trials}")
                finally:
                    trials = trials + 1
                    time.sleep(delay)
                    if trials == tries_numb:
                        if debug:
                            log_max_trials(debug)
                            log_unable_to_start(debug)
                        else:
                            print(
                                "We could not access the cloud to check the status of the recording \n We cannot ensure the recording integrity, to be sure please restart the recording in a few minutes"
                            )
                        raise Exception

            return f(*args, **kwargs)

        return retry_fun

    return retry_decorator


def exit_system() -> None:
    """Exit the system."""
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)


def stop_ongoing_recording(status_details, device_id, password):
    start_index = status_details.find("ID:") + 6
    end_index = status_details.find("}")
    # Extract the recording IDs as a string
    recording_ids_str = status_details[start_index:end_index]
    # Split the string by comma to get individual recording IDs
    recording_ids = recording_ids_str.split(", ")
    # Remove the surrounding single quotes from each recording ID
    recording_ids = [recording_id.strip("'") for recording_id in recording_ids]
    num = len(recording_ids)
    successfully_stopped = 0
    for rec in recording_ids:
        with requests.Session() as session:
            record_url_first = f"{settings.REST_API_LOGIN}"
            record_url_second = f"devices/{device_id}/recordings/{rec}/status"
            record_url = record_url_first + record_url_second
            payload = RecordingStatusOut(
                stopped=True,
                status="COMPLETED",
                message="Trying to stop the recording",
            )
            headers = {
                "accept": "application/json",
                "Content-Type": "application/json",
            }
            result = session.put(
                record_url,
                headers=headers,
                data=payload.json(),
                auth=(device_id, password),
            )
            if result.status_code == 200 or result.status_code == 201:
                log_rec_ongoing_stopped_successfully(debug=True, rec=rec)
                successfully_stopped = successfully_stopped + 1

            else:
                log_couldnot_stop_ongoing_rec(debug=True, rec=rec)
                print(result.text)

    if successfully_stopped == int(num):
        log_able_to_start(debug)
    else:
        print(
            f"We could not stop {int(num)-successfully_stopped} recordings, try to stop the resting recordings manually with the given scripts"
        )
    exit_system()


def stop_rec(device_id, recording_id, password=""):
    if password == "":
        password = input("Type here your password:")
    with requests.Session() as session:
        record_url_first = f"{settings.REST_API_LOGIN}"
        record_url_second = f"devices/{device_id}/recordings/{recording_id}/status"
        record_url = record_url_first + record_url_second
        payload = RecordingStatusOut(
            stopped=True,
            status="COMPLETED",
            message="Trying to stop the recording",
        )
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        result = session.put(
            record_url,
            headers=headers,
            data=payload.json(),
            auth=(device_id, password),
        )
        if result.status_code == 200 or result.status_code == 201:
            log_rec_ongoing_stopped_successfully(debug=True, rec=recording_id)

        else:
            log_couldnot_stop_ongoing_rec(debug=True, rec=recording_id)
            print(result.text)


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
    print("Mac address is valid")
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


def unpack_from_queue(package):
    """Unpack data from the queue filled with BLE data

    Args:
        package (dict): BLE data package

    Returns:
        timestamp: Timestamp of the data
        deviceID: Device ID of the data
        data: Data from the BLE package
        stop: Boolean to stop the cloud streaming
        impedance: Impedance data
    """
    # check if "timestamp" is in the package
    if "timestamp" in package:
        timestamp = package["timestamp"]
    else:
        timestamp = None

    # chek if deviceID is in the package
    if "deviceID" in package:
        device_id = package["deviceID"]
    else:
        device_id = None

    # check if "data" is in the package
    if "data" in package:
        data = package["data"]
    else:
        data = None

    # check if "type" is in the package
    if "stop" in package:
        stop = package["stop"]
    else:
        stop = None

    # check if impedance is in the package
    if "impedance" in package:
        impedance = package["impedance"]
    else:
        impedance = None

    return (timestamp, device_id, data, stop, impedance)


async def unpack_and_load_data(data_model, data_queue):
    """Get data from the queue and pack it into a dataclass"""
    package = await data_queue.get()
    (
        device_timestamp,
        device_id,
        data,
        stop,
        impedance,
    ) = unpack_from_queue(package)

    if data is not None:
        data_model.payload = data
    if device_timestamp is not None:
        data_model.deviceTimestamp = device_timestamp
    if device_id is not None:
        data_model.deviceID = device_id
    if stop is not None:
        data_model.stop = stop
    if impedance is not None:
        data_model.impedance = impedance
    return data_model, data_queue
