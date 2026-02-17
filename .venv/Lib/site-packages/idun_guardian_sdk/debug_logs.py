"""
This module contains the functions that are used to log the debug messages.
"""

import logging
import time

logger = logging.getLogger("idun_guardian_sdk")


def log_device_status(connection_status):
    logger.debug(f"[BLE]: Current Device Status={connection_status}")


def log_calling_function_while_retrying(string):
    logger.debug(string)


def log_sending_start_rec_info():
    logger.debug("[API]: Sending to the cloud information that recording started")


def log_api_result_details(details):
    logger.debug(f"[API]: {details}")


def log_api_status(status):
    logger.debug(f"[API]: Status Code {status}")


def log_couldnot_stop_ongoing_rec(rec):
    logger.warning(
        f"[API]: Could not stop recording {rec}, please try another time or stop them manually with the given code"
    )


def log_rec_ongoing_stopped_successfully(rec):
    logger.debug(f"[API]: Recording id {rec}, was successfully_stopped")


def log_able_to_start():
    logger.debug("[API]: You are now able to start a new recording")


def log_message_retry(trials):
    logger.debug(f"Trials Number {trials}")


def log_unable_to_start():
    logger.warning(
        f"[API]: We could not start the recording. If it is our responsability we will retry to fix the problem. \n Error: {err}"
    )


def log_unable_to_stop(err):
    logger.debug(f"[API]: We could not stop the recording, we will retry to fix the problem. \n Error: {err}")


def log_max_trials():
    logger.warning(
        "[API]: We could not access the cloud to check the status of the recording \n We cannot ensure the recording integrity, to be sure please restart the recording in a few minutes"
    )


def log_successfully_started():
    logger.debug("[API]: The Recording has been correctly initialized")


def log_warning_stop_message():
    logger.debug(
        "[API]: This is a Warning Message!\n We can not ensure the integrity of the whole recording in our Cloud because some strange Error occurred when sending the stop command to our Backend \n Try to Download the recording"
    )


def log_not_able_to_connect_with_the_cloud(string: str, status: str):
    logger.debug(
        f"[API]: Not able to {string} the connection with the cloud , exiting with error number {status}, will re-try"
    )


def log_not_client_found():
    logger.debug("[BLE]: Client not initialized")


def log_exception_in_disconnecting():
    logger.debug("[BLE]: Cannot disconnect, device already disconnected")


def log_exception_unable_to_find_MACaddress(err):
    logger.debug(
        f"[BLE]: The following error occurred when trying to find the device mac ID:{err}",
    )


def log_exception_while_trying_connection(err):
    logger.debug(f"[BLE]: Exception raised while trying to connect:{err}")


def log_timeout_while_trying_connection():
    logger.debug("[API]: Timeout for connection failure, will try to reconnect")


def logging_connection(websocket_resource_url):
    logger.debug(
        "[API]: Connected to websocket resource url: %s",
        websocket_resource_url,
    )
    logger.debug("[API]: Sending data to the cloud")


def logging_ping_error(error, retry_time):
    logger.debug("[API]: Ping interruption: %s", error)
    logger.debug("[API]: Ping failed, connection closed")
    logger.debug(
        "[API]: Trying to reconnect in %s seconds",
        retry_time,
    )


def logging_not_empty() -> None:
    """Log the queue is not empty."""
    logger.debug("[API]: Data queue is not empty, waiting for last timestamp")


def log_error_in_sending_stop(error):
    logger.debug(
        "[API]: Error in sending stop signal to the cloud: %s",
        error,
    )


def log_error_in_sending_stop_ble(error):
    logger.debug(
        "[BLE]: Error in loading stop signal to the cloud: %s",
        error,
    )


def logging_reconnection():
    logger.debug("[API]: Trying to reconnect to the cloud...")


def logging_empty():
    logger.debug("[API]: Device queue is empty, sending computer time")


def logging_cloud_termination():
    logger.debug("[API]: Terminating cloud connection")


def logging_gaieerror(error, retry_time):
    logger.debug("[API]: Interruption in connecting to the cloud: %s", error)
    logger.debug("[API]: Retrying connection in %s sec ", retry_time)


def logging_connection_refused(error, retry_time):
    logger.debug("[API]: Interruption in connecting to the cloud: %s", error)
    logger.debug("Cannot connect to API endpoint. Please check the URL and try again.")
    logger.debug("Retrying connection in {} seconds".format(retry_time))


def logging_cancelled_error():
    logger.debug("[API]: Error in sending data to the cloud: %s")
    logger.debug("[API]: Re-establishing cloud connection in exeption")
    logger.debug("[API]: Fetching last package from queue")


def logging_connecting_to_cloud():
    logger.debug("[API]: Connecting to cloud...")


def logging_waiting_for_stop_receipt():
    logger.debug("[API]: Waiting for stop receipt")


def logging_api_completed():
    logger.debug("[API]: -----------  API client is COMPLETED ----------- ")


def logging_succesfull_stop():
    logger.debug("[BLE]: Recording successfully stopped")


def logging_searching():
    logger.debug("[BLE]: Searching for MAC address")


def logging_device_info(mac_address, firmware_decoded):
    logger.debug("[BLE]: Device ID (based on MAC address is): %s", mac_address)
    logger.debug("[BLE]: Firmware version: %s", firmware_decoded)


def logging_device_not_found(break_time):
    logger.info(f"[BLE]: No IGEB device found, trying again in {break_time} seconds")


def logging_device_found(ble_device_list):
    logger.debug("[BLE]: One IGEB device found, assinging address %s", ble_device_list[0])


def logging_trying_to_connect(device_address):
    logger.debug("[BLE]: Trying to connect to %s.....", device_address)


def logging_connected(device_address):
    logger.debug("[BLE]: Connected to %s", device_address)


def logging_disconnected_recognised():
    logger.debug("[BLE]: Callback function recognised a disconnection.")


def logging_batterylevel(battery_level):
    logger.debug(
        "[BLE]: Battery level: %d%%",
        int.from_bytes(battery_level, byteorder="little"),
    )


def logging_sending_start():
    logger.debug("[BLE]: Sending start commands")


def logging_subscribing_eeg_notification():
    logger.debug("[BLE]: Subscribing EEG notification")


def logging_subscribing_battery_notification():
    logger.debug("[BLE]: Subscribing battery notification")


def logging_sending_disconnect():
    logger.debug("[BLE]: Sending disconnect command to device")


def logging_turn_led_on():
    logger.debug("[BLE]: Turning LED on")


def logging_device_lost_give_up():
    logger.debug("[BLE]: Device lost, terminating...")


def logging_time_reached(original_time):
    logger.debug(
        "[BLE]: Recording stopped, time reached : %s",
        round(time.time() - original_time, 2),
    )


def logging_timeout_reached():
    logger.debug("[BLE]: Time out reached")


def logging_ble_client_lost(error):
    logger.error("[BLE]: Error in bluetooth client: %s", error)


def logging_ensuring_ble_disconnected():
    logger.debug("[BLE]: Ensuring device is disconnected")


def logging_device_info_uuid(service):
    logger.debug("[Service] %s: %s", service.uuid, service.description)


def logging_device_info_characteristic(char, value):
    logger.info(
        "\t[Characteristic] %s: (Handle: %s) (%s) \
                | Name: %s, Value: %s ",
        char.uuid,
        char.handle,
        ",".join(char.properties),
        char.description,
        value,
    )


def logging_device_description_list(char, value):
    logger.info("%s : %s", char.description, str(value))


def logging_device_connection_failed(err):
    logger.error("[BLE]: Device connection failed - %s", err)


def logging_getting_impedance(impedance_display_time):
    logger.debug("[BLE]: Getting impedance measurement")
    logger.debug("[BLE]: Impedance display time: %s seconds", impedance_display_time)


def logging_starting_impedance_measurement():
    logger.debug("[BLE]: Starting impedance measurement")


def logging_displaying_impedance():
    logger.debug("[BLE]: Displaying impedance measurement")


def logging_stopping_impedance_measurement():
    logger.debug("[BLE]: Stopping impedance measurement")


def logging_ble_complete():
    logger.debug("[BLE]: -----------  BLE client is COMPLETED ----------- ")


def loggig_ble_init():
    logger.debug("[BLE]: BLE client initiliazed")


def logging_batterylevel_int(value):
    logger.debug("Battery level: %s%%", value)


def logging_cloud_not_receiving(credit_reimbursement):
    # This wifi connection works with a credit system. If a receipt is found, then the credits are replenished.
    # with one credit per package in the receipt. For each message without a receipt, the credits are reduced by one.
    # If the credits are reduced to zero, the package that is sent is the fake data package until a receipt is received.
    # In which case the credits are replenished and the real data is sent.
    logger.warning("Data is not being received by cloud")
    logger.warning(f"Resending last package again in {credit_reimbursement} seconds")
