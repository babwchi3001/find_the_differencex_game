"""
This module contains the functions that are used to log the debug messages.
"""
import logging
import time


def log_device_status(debug, connection_status):
    if debug:
        logging.info(f"[BLE]: Current Device Status={connection_status}")


def log_calling_function_while_retrying(debug, string: str):
    if debug:
        logging.info(string)


def log_sending_start_rec_info(debug):
    if debug:
        logging.info("[API]: Sending to the cloud information that recording started")


def log_api_result_details(debug, details):
    if debug:
        logging.info(f"[API]: {details}")


def log_api_status(debug, status):
    if debug:
        logging.info(f"[API]: Status Code {status}")


def log_connection_flag(debug, flag_value):
    if debug:
        logging.info(f"[BLE]: Connection: {flag_value}")


def log_connection_initialize_flag(debug, flag_value):
    if debug:
        logging.info(f"[BLE]: Initialize: {flag_value}")


def log_couldnot_stop_ongoing_rec(debug, rec):
    if debug:
        logging.warning(
            f"[API]: Could not stop recording {rec}, please try another time or stop them manually with the given code"
        )


def log_rec_ongoing_stopped_successfully(debug, rec):
    if debug:
        logging.info(f"[API]: Recording id {rec}, was successfully_stopped")


def log_able_to_start(debug):
    if debug:
        logging.info("[API]: You are now able to start a new recording")


def log_message_retry(debug, trials):
    if debug:
        logging.info(f"Trials Number {trials}")


def log_rec_stopped(debug):
    if debug:
        logging.info("[API]: The Recording has been correctly stopped")


def log_unable_to_start(debug):
    if debug:
        logging.warning(
            f"[API]: We could not start the recording. If it is our responsability we will retry to fix the problem. \n Error: {err}"
        )


def log_unable_to_stop(debug, err):
    if debug:
        logging.info(
            f"[API]: We could not stop the recording, we will retry to fix the problem. \n Error: {err}"
        )


def log_max_trials(debug):
    if debug:
        logging.warning(
            "[API]: We could not access the cloud to check the status of the recording \n We cannot ensure the recording integrity, to be sure please restart the recording in a few minutes"
        )


def log_successfully_started(debug):
    if debug:
        logging.info("[API]: The Recording has been correctly initialized")


def log_warning_stop_message(debug):
    if debug:
        logging.info(
            "[API]: This is a Warning Message!\n We can not ensure the integrity of the whole recording in our Cloud because some strange Error occurred when sending the stop command to our Backend \n Try to Download the recording"
        )


def log_not_able_to_connect_with_the_cloud(debug, string: str, status: str):
    if debug:
        logging.info(
            f"[API]: Not able to {string} the connection with the cloud , exiting with error number {status}, will re-try"
        )


def log_not_client_found(debug):
    if debug:
        logging.info("[BLE]: Client not initialized")


def log_exception_in_disconnecting(debug):
    if debug:
        logging.info("[BLE]: Cannot disconnect, device already disconnected")


def log_no_connection_established(debug):
    if debug:
        logging.info(
            "[API]: No Connection has been established, will disconnect and try to reconnect again"
        )


def log_exception_unable_to_find_MACaddress(debug, err):
    if debug:
        logging.info(
            f"[BLE]: The following error occurred when trying to find the device mac ID:{err}",
        )


def log_exception_while_trying_connection(debug, err):
    if debug:
        logging.info(f"[BLE]: Exception raised while trying to connect:{err}")


def log_timeout_while_trying_connection(debug):
    if debug:
        logging.info("[API]: Timeout for connection failure, will try to reconnect")


def log_device_not_connected_cannot_stop(debug):
    if debug:
        logging.info("[API]: Device not connected, cannot stop")


def log_first_message(data_model, package_receipt, debug):
    if debug:
        logging.info("[API]: First package sent")
        logging.info(
            "[API]: data_model.stop = %s",
            data_model.stop,
        )
        logging.info(
            "[API]: data_model.deviceID = %s",
            data_model.deviceID,
        )
        logging.info(
            "[API]: data_model.recordingID = %s",
            data_model.recordingID,
        )
        logging.info(
            "[API]: First package receipt: %s",
            package_receipt,
        )


def log_final_message(data_model, package_receipt, debug):
    if debug:
        logging.info("[API]: Last package sent")
        logging.info(
            "[API]: data_model.stop = %s",
            data_model.stop,
        )
        logging.info(
            "[API]: data_model.deviceID = %s",
            data_model.deviceID,
        )
        logging.info(
            "[API]: data_model.recordingID = %s",
            data_model.recordingID,
        )
        logging.info(
            "[API]: Last package receipt: %s",
            package_receipt,
        )
        logging.info("[API]: Cloud connection successfully terminated")
        logging.info("[API]: Breaking inner loop of API client")


def logging_connection(websocket_resource_url, debug):
    if debug:
        logging.info(
            "[API]: Connected to websocket resource url: %s",
            websocket_resource_url,
        )
        logging.info("[API]: Sending data to the cloud")


def logging_break(debug):
    if debug:
        logging.info("[API]: Breaking API client while loop")


def logging_ping_error(error, retry_time, debug):
    if debug:
        logging.info("[API]: Ping interruption: %s", error)
        logging.info("[API]: Ping failed, connection closed")
        logging.info(
            "[API]: Trying to reconnect in %s seconds",
            retry_time,
        )


def logging_not_empty(debug: bool) -> None:
    """Log the queue is not empty."""
    if debug:
        logging.info("[API]: Data queue is not empty, waiting for last timestamp")


def log_interrupt_error(error, debug):
    if debug:
        logging.info(
            "[API]: Interuption in sending or receiving data to the cloud: %s",
            error,
        )


def log_error_in_sending_stop(error, debug):
    if debug:
        logging.info(
            "[API]: Error in sending stop signal to the cloud: %s",
            error,
        )


def log_error_in_sending_stop_ble(error, debug):
    if debug:
        logging.info(
            "[BLE]: Error in loading stop signal to the cloud: %s",
            error,
        )


def logging_connection_closed(debug):
    if debug:
        logging.info("[API]: Websocket client connection closed")


def logging_reconnection(debug):
    if debug:
        logging.info("[API]: Ping successfull, connection alive and continue..")
        logging.info("Try to ping websocket successfull")


def logging_empty(debug):
    if debug:
        logging.info("[API]: Device queue is empty, sending computer time")


def logging_cloud_termination(debug):
    if debug:
        logging.info("[API]: Terminating cloud connection")


def logging_gaieerror(error, retry_time, debug):
    if debug:
        logging.info("[API]: Interruption in connecting to the cloud: %s", error)
        logging.info("[API]: Retrying connection in %s sec ", retry_time)


def logging_connection_refused(error, retry_time, debug):
    if debug:
        logging.info("[API]: Interruption in connecting to the cloud: %s", error)
        logging.info(
            "Cannot connect to API endpoint. Please check the URL and try again."
        )
        logging.info("Retrying connection in {} seconds".format(retry_time))


def logging_cancelled_error(debug):
    if debug:
        logging.info("[API]: Error in sending data to the cloud: %s")
        logging.info("[API]: Re-establishing cloud connection in exeption")
        logging.info("[API]: Fetching last package from queue")


def logging_connecting_to_cloud(debug):
    if debug:
        logging.info("[API]: Connecting to cloud...")


def logging_waiting_for_stop_receipt(debug):
    if debug:
        logging.info("[API]: Waiting for stop receipt")


def logging_api_completed(debug):
    if debug:
        logging.info("[API]: -----------  API client is COMPLETED ----------- ")


def logging_succesfull_stop(debug):
    if debug:
        logging.info("[BLE]: Recording successfully stopped")


def logging_searching(debug):
    if debug:
        logging.info("[BLE]: Searching for MAC address")


def logging_device_info(debug, mac_address, firmware_decoded):
    if debug:
        logging.info("[BLE] Device ID (based on MAC address is): %s", mac_address)
        logging.info("[BLE]: Firmware version: %s", firmware_decoded)


def logging_device_not_found(debug, break_time):
    if debug:
        logging.info(
            f"[BLE]: No IGEB device found, trying again in {break_time} seconds"
        )


def logging_device_found(debug, ble_device_list):
    if debug:
        logging.info(
            "[BLE]: One IGEB device found, assinging address %s", ble_device_list[0]
        )


def logging_device_address(debug, device_address):
    if debug:
        logging.info("[BLE]: Received address as %s", device_address)


def logging_trying_to_connect(debug, device_address):
    if debug:
        logging.info("[BLE]: Trying to connect to %s.....", device_address)


def logging_connected(debug, device_address):
    if debug:
        logging.info("[BLE]: Connected to %s", device_address)


def logging_disconnected_recognised(debug):
    if debug:
        logging.info("[BLE]: Callback function recognised a disconnection.")


def logging_batterylevel(debug, battery_level):
    if debug:
        logging.info(
            "[BLE]: Battery level: %d%%",
            int.from_bytes(battery_level, byteorder="little"),
        )


def logging_sending_start(debug):
    if debug:
        logging.info("[BLE]: Sending start commands")


def logging_subscribing_eeg_notification(debug):
    if debug:
        logging.info("[BLE]: Subscribing EEG notification")


def logging_subscribing_battery_notification(debug):
    if debug:
        logging.info("[BLE]: Subscribing battery notification")


def logging_sending_stop(debug):
    if debug:
        logging.info("[BLE]: Stop command loaded into queue")


def logging_giving_time_api(debug):
    if debug:
        logging.info("[BLE]: Giving time to API client to send data")


def logging_sending_stop_device(debug):
    if debug:
        logging.info("[BLE]: Sending stop command to device")


def logging_sending_disconnect(debug):
    if debug:
        logging.info("[BLE]: Sending disconnect command to device")


def logging_turn_ble_on(debug):
    if debug:
        logging.info("[BLE]: Turning BLE on")


def logging_turn_led_on(debug):
    if debug:
        logging.info("[BLE]: Turning LED on")


def logging_recording_successfully_stopped(debug):
    if debug:
        logging.info("[BLE]: Recording successfully stopped")


def logging_keyboard_interrupt(debug):
    if debug:
        logging.info("[BLE]: KeyboardInterrupt applied, terminating...")
        logging.info(
            "[BLE]: Sending stop signal to device and cloud, please wait a moment ..."
        )


def logging_stop_send(debug):
    if debug:
        logging.info(
            "[API]: Sending stop signal to device and cloud, please wait a moment ..."
        )


def logging_device_lost_give_up(debug):
    if debug:
        logging.info("[BLE]: Device lost, terminating...")


def logging_trying_to_connect_again(debug, try_to_connect_timeout):
    if debug:
        logging.warning(
            " [BLE] Connection lost, will try to reconnect %s more times",
            try_to_connect_timeout,
        )


def logging_device_connected_general(debug):
    if debug:
        logging.info("[BLE]: Device connected")


def logging_recording_started(debug):
    if debug:
        logging.info("[BLE]: Recording successfully started")


def logging_time_reached(debug, original_time):
    if debug:
        logging.info(
            "[BLE]: Recording stopped, time reached : %s",
            round(time.time() - original_time, 2),
        )


def logging_timeout_reached(debug):
    if debug:
        logging.info("[BLE]: Time out reached")


def logging_ble_client_lost(debug, error):
    if debug:
        logging.error("[BLE]: Error in bluetooth client: %s", error)


def logging_ensuring_ble_disconnected(debug):
    if debug:
        logging.info("[BLE]: Ensuring device is disconnected")


def logging_device_info_uuid(debug, service):
    if debug:
        logging.info("[Service] %s: %s", service.uuid, service.description)


def logging_device_info_characteristic(debug, char, value):
    if debug:
        logging.info(
            "\t[Characteristic] %s: (Handle: %s) (%s) \
                | Name: %s, Value: %s ",
            char.uuid,
            char.handle,
            ",".join(char.properties),
            char.description,
            value,
        )


def logging_device_description_list(debug, char, value):
    if debug:
        logging.info("%s : %s", char.description, str(value))


def logging_device_connection_failed(debug, err):
    if debug:
        logging.error("[BLE]: Device connection failed - %s", err)


def logging_reading_battery_level(debug):
    if debug:
        logging.info("[BLE]: Reading battery level")


def logging_getting_impedance(debug, impedance_display_time):
    if debug:
        logging.info("[BLE]: Getting impedance measurement")
        logging.info(
            "[BLE]: Impedance display time: %s seconds", impedance_display_time
        )


def logging_starting_impedance_measurement(debug):
    if debug:
        logging.info("[BLE]: Starting impedance measurement")


def logging_subscribing_impedance_notification(debug):
    if debug:
        logging.info("[BLE]: Subscribing impedance measurement")


# create logging functions for start impedance command, displaying impedance and stop impedance command
def logging_starting_impedance_measurement_commands(debug):
    if debug:
        logging.info("[BLE]: Sending start impedance commands")


def logging_displaying_impedance(debug):
    if debug:
        logging.info("[BLE]: Displaying impedance measurement")


def logging_stopping_impedance_measurement(debug):
    if debug:
        logging.info("[BLE]: Stopping impedance measurement")


def logging_ble_complete(debug):
    if debug:
        logging.info("[BLE]: -----------  BLE client is COMPLETED ----------- ")


def loggig_ble_init(debug):
    if debug:
        logging.info("[BLE]: BLE client initiliazed")


def logging_batterylevel_int(debug, value):
    if debug:
        logging.info("Battery level: %s%%", value)


def logging_cloud_not_receiving(debug, credit_reimbursement):
    # This wifi connection works with a credit system. If a receipt is found, then the credits are replenished.
    # with one credit per package in the receipt. For each message without a receipt, the credits are reduced by one.
    # If the credits are reduced to zero, the package that is sent is the fake data package until a receipt is received.
    # In which case the credits are replenished and the real data is sent.
    if debug:
        logging.warning("Data is not being received by cloud")
        logging.warning(
            f"Resending last package again in {credit_reimbursement} seconds"
        )
