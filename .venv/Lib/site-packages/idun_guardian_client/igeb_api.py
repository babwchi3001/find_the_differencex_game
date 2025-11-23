"""
Guardian API websocket utilities.
"""
import os
import json
from dataclasses import dataclass, asdict
import socket
import datetime
import time
import asyncio
from typing import Union
import requests
from requests.auth import AuthBase
import websockets
import time
from typing import Optional
from dotenv import load_dotenv

from .config import settings
from .igeb_utils import unpack_from_queue
from .mock_utils import mock_cloud_package
from .debug_logs import *
from .igeb_utils import (
    retry,
    exit_system,
    stop_ongoing_recording,
    string_detail_to_log,
)
from idun_data_models import RecordingIn, RecordingStatusOut
import idun_data_models

load_dotenv()

FILTER_EEG_INFERENCE = "bp_filter_eeg"
RAW_EEG_INFERENCE = "raw_eeg"
PACKAGE_RECEIPT = "SequenceNumber"

class TokenAuth(AuthBase):
    def __init__(self, token, auth_scheme='Bearer'):
        self.token = token
        self.auth_scheme = auth_scheme

    def __call__(self, request):
        request.headers['Authorization'] = f'{self.auth_scheme} {self.token}'
        return request


class GuardianAPI:
    """Main Guardian API client."""

    def __init__(self, debug: bool = True) -> None:
        """Initialize Guardian API client.

        Args:
            debug (bool, optional): Enable debug logging. Defaults to True.
        """
        self.debug: bool = debug
        self.ping_timeout: int = 2
        self.retry_time: int = 2
        self.base64string_len: int = 236
        self.first_message_check = True
        self.final_message_sent = False
        self.payload_valid = True
        self.sample_rate = 250
        self.sentinal = object()
        self.encrypted_buffer_size = 3750  # 5 minutes => (5 * 60 * 250) / 20 = 3750
        self.decrypted_buffer_size = 75000  # 5 minutes => (5 * 60 * 250) = 75000
        self.encrypted_data_queue: asyncio.Queue = asyncio.Queue(
            maxsize=self.encrypted_buffer_size
        )
        self.decrypted_bandpass_eeg_queue: asyncio.Queue = asyncio.Queue(
            maxsize=self.decrypted_buffer_size
        )
        self.decrypted_raw_eeg_queue: asyncio.Queue = asyncio.Queue(
            maxsize=self.decrypted_buffer_size
        )
        self.initial_receipt_timeout = 15
        self.runtime_receipt_timeout: float = 1  # Increase if slow connection
        self.current_timeout = self.initial_receipt_timeout
        self.initial_bi_directional_timeout = 15
        self.runtime_bi_directional_timeout: float = 5  # Increase if slow connection
        self.sending_time_limit = 0.01
        self.bi_directional_timeout = self.initial_bi_directional_timeout
        self.last_saved_time = time.time()
        self.connected = False
        self.data_model = GuardianDataModel(None, None, None, None, None, False)
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None  # type: ignore
        self.final_receipt_got = False
        self.deviceID = ""
        self.guardian_rec: RecordingIn | None = None
        self.password = ""
        self.rec_started_time = None
        self.rec_ended_time = None

    async def connect_ws_api(
        self,
        data_queue: asyncio.Queue,
        device_id: str = "deviceMockID",
        recording_id: str = "dummy_recID",
        impedance_measurement: bool = False,
    ) -> None:
        """Connect to the Guardian API websocket.

        Args:
            data_queue (asyncio.Queue): Data queue from the BLE client
            deviceID (str, optional): Device ID. Defaults to "deviceMockID".
            recordingID (str, optional): Recording ID. Defaults to "dummy_recID".

        Raises:
            Exception: If the websocket connection fails
        """

        @retry(debug=True)
        def check_recording_started():
            device_id = self.deviceID
            recording_id = self.guardian_rec.recordingID
            if self.password == "":
                self.password = input("\nEnter your new password here: ")
            with requests.Session() as session:
                record_url_first = f"{settings.REST_API_LOGIN}"
                record_url_second = f"devices/{device_id}/recordings"
                record_url = record_url_first + record_url_second
                payload = (self.guardian_rec).json()
                headers = {
                    "accept": "application/json",
                    "Content-Type": "application/json",
                }
                result = session.post(
                    record_url,
                    headers=headers,
                    data=payload,
                    auth=TokenAuth(token=self.password, auth_scheme=''),
                )
                status = result.status_code
                status_details = string_detail_to_log(result.text)

                if status == 200 or status == 201:
                    log_successfully_started(self.debug)
                    self.rec_started_time = datetime.datetime.fromtimestamp(time.time())
                else:
                    self.password = ""
                    log_api_status(self.debug, status)
                    log_api_result_details(self.debug, status_details)
                    raise Exception

                if "recording ongoing" in status_details:
                    print("Going to stop existing rec:")
                    stop_ongoing_recording(status_details, device_id, self.password)

        @retry(debug=True)
        def check_recording_ended():
            device_id = self.deviceID
            recording_id = self.guardian_rec.recordingID
            self.rec_ended_time = datetime.datetime.fromtimestamp(time.time())
            with requests.Session() as session:
                record_url_first = f"{settings.REST_API_LOGIN}"
                record_url_second = (
                    f"devices/{device_id}/recordings/{recording_id}/status"
                )
                record_url = record_url_first + record_url_second
                payload = RecordingStatusOut(
                    stopped=True,
                    status="COMPLETED",
                    message="Trying to stop the recording",
                    createdAT=self.rec_started_time,
                    stoppedAT=self.rec_ended_time,
                )
                headers = {
                    "accept": "application/json",
                    "Content-Type": "application/json",
                }
                result = session.put(
                    record_url,
                    headers=headers,
                    data=(payload).json(),
                    auth=TokenAuth(token=self.password, auth_scheme=''),
                )
                if result.status_code == 200:
                    log_rec_stopped(self.debug)

                else:
                    print(result.status_code)
                    print(result.text)

        def reset_data_model():
            self.data_model.payload = None
            self.data_model.impedance = None

        async def pack_encrypted_queue():
            if not self.encrypted_data_queue.full():
                await self.encrypted_data_queue.put(
                    [self.data_model.deviceTimestamp, self.data_model.payload]
                )
            else:
                await self.encrypted_data_queue.get()

        def pack_decrypted_queue(message):
            if not self.decrypted_bandpass_eeg_queue.full():
                if FILTER_EEG_INFERENCE in message:
                    self.decrypted_bandpass_eeg_queue.put_nowait(
                        message[FILTER_EEG_INFERENCE]
                    )
            else:
                self.decrypted_bandpass_eeg_queue.get_nowait()
            if not self.decrypted_raw_eeg_queue.full():
                if RAW_EEG_INFERENCE in message:
                    self.decrypted_raw_eeg_queue.put_nowait(message[RAW_EEG_INFERENCE])
            else:
                self.decrypted_raw_eeg_queue.get_nowait()

        async def unpack_and_load_data():
            """Get data from the queue and pack it into a dataclass"""
            data_valid = False
            reset_data_model()
            package = await data_queue.get()
            (
                device_timestamp,
                device_id,
                data,
                stop,
                impedance,
            ) = unpack_from_queue(package)

            if data is not None:
                if len(data) == self.base64string_len:
                    self.data_model.payload = data
                    data_valid = True

            if impedance is not None:
                if isinstance(impedance, int):
                    self.data_model.impedance = impedance
                    data_valid = True

            if device_timestamp is not None:
                self.data_model.deviceTimestamp = device_timestamp

            if device_id is not None:
                self.data_model.deviceID = device_id

            if stop is not None:
                self.data_model.stop = stop
                if stop is True:
                    data_valid = True

            return data_valid

        async def create_timestamp(debug):
            """Create a timestamp for the data"""
            if data_queue.empty():
                logging_empty(debug)  # Fetch the current time from the device
                device_timestamp = datetime.datetime.now().astimezone().isoformat()
            else:
                logging_not_empty(debug)
                package = (
                    await data_queue.get()
                )  # Fetch the timestamp from the BLE package
                (device_timestamp, _, _, _, _) = unpack_from_queue(package)
            return device_timestamp

        async def unpack_and_load_data_termination():
            """Get data from the queue and pack it into a dataclass"""
            logging_cloud_termination(self.debug)
            self.data_model.payload = "STOP_CANCELLED"
            self.data_model.stop = True
            device_timestamp = await create_timestamp(self.debug)
            if device_timestamp is not None:
                self.data_model.deviceTimestamp = device_timestamp

        async def send_messages():
            while True:
                if not self.connected:
                    break

                if await unpack_and_load_data():
                    await asyncio.shield(
                        asyncio.sleep(self.sending_time_limit)
                    )  # Wait as to not overload the cloud
                    await asyncio.shield(
                        self.websocket.send(json.dumps(asdict(self.data_model)))
                    )
                    await asyncio.shield(pack_encrypted_queue())

                if self.data_model.stop:
                    logging_stop_send(self.debug)
                    self.current_timeout = (
                        1000  # Wait until necessary for the stop to be sent
                    )
                    self.final_message_sent = True
                    while not self.final_receipt_got:
                        # It will loop in here and not update the
                        # data until the stop is sent
                        logging_waiting_for_stop_receipt(self.debug)
                        await asyncio.sleep(1)
                    try:
                        check_recording_ended()

                    except Exception as e:
                        log_unable_to_stop(self.debug, e)
                    break

        async def receive_messages():
            self.last_saved_time = time.time()
            while True:
                if not self.connected:
                    break

                message_str = await asyncio.shield(
                    asyncio.wait_for(
                        self.websocket.recv(), timeout=self.current_timeout
                    )
                )

                if (
                    FILTER_EEG_INFERENCE in message_str
                    or RAW_EEG_INFERENCE in message_str
                ):
                    self.bi_directional_timeout = self.runtime_bi_directional_timeout
                    message = json.loads(message_str)
                    self.last_saved_time = time.time()
                    pack_decrypted_queue(message)

                elif PACKAGE_RECEIPT in message_str:
                    self.current_timeout = self.runtime_receipt_timeout
                    if self.first_message_check:
                        self.first_message_check = False
                        log_first_message(
                            self.data_model,
                            message_str,
                            self.debug,
                        )
                    if self.final_message_sent:
                        log_final_message(
                            self.data_model,
                            message_str,
                            self.debug,
                        )
                        self.final_receipt_got = True
                        break

                bi_directional_timeout(impedance_measurement)

        def bi_directional_timeout(impedance_measurement):
            time_without_data = time.time() - self.last_saved_time
            if (
                time_without_data > self.bi_directional_timeout
                and not impedance_measurement
            ):
                raise asyncio.TimeoutError

        def once_initialise_variables():
            # initiate flags
            self.first_message_check = True
            self.final_message_sent = False
            self.data_model = GuardianDataModel(
                None, device_id, recording_id, None, None, False
            )

        def on_connection_initialise_variables():
            self.first_message_check = True
            self.connected = True
            self.bi_directional_timeout = self.initial_bi_directional_timeout
            self.current_timeout = self.initial_receipt_timeout

        async def handle_cancelled_error():
            while True:
                try:
                    async with websockets.connect(  # type: ignore
                        settings.WS_IDENTIFIER + "?authorization=" + self.password
                    ) as self.websocket:
                        logging_cancelled_error(self.debug)
                        await unpack_and_load_data_termination()
                        await self.websocket.send(
                            json.dumps(asdict(self.data_model))
                        )  # send what? the recording class? i have to use the new package to build a recording class?
                        package_receipt = await self.websocket.recv()
                        log_final_message(
                            self.data_model,
                            package_receipt,
                            self.debug,
                        )
                        self.final_message_sent = True
                        if self.data_model.stop:
                            try:
                                check_recording_ended()
                            except Exception as e:
                                log_unable_to_stop(self.debug, e)

                        break

                except Exception as err:
                    await asyncio.sleep(self.ping_timeout)
                    log_error_in_sending_stop(err, self.debug)
                    continue

        once_initialise_variables()

        while True:
            logging_connecting_to_cloud(self.debug)
            try:
                if self.password == "":
                    self.password = input("\nEnter your new password here: ")
                async with websockets.connect(settings.WS_IDENTIFIER + "?authorization=" + self.password) as self.websocket:  # type: ignore
                    if self.rec_started_time == None:
                        try:
                            log_sending_start_rec_info(self.debug)
                            check_recording_started()
                        except Exception:
                            exit_system()
                    try:
                        on_connection_initialise_variables()
                        # for the websocket we want to increase to initial timeout each time
                        logging_connection(settings.WS_IDENTIFIER, self.debug)
                        send_task = asyncio.create_task(send_messages())
                        receive_task = asyncio.create_task(receive_messages())
                        await asyncio.gather(send_task, receive_task)

                    except (
                        websockets.exceptions.ConnectionClosed,  # type: ignore
                    ) as error:
                        try:
                            logging_connection_closed(self.debug)
                            self.connected = False
                            await asyncio.shield(asyncio.sleep(self.ping_timeout))
                            logging_reconnection(self.debug)
                            self.bi_directional_timeout = (
                                self.initial_bi_directional_timeout
                            )
                            continue
                        except asyncio.CancelledError:
                            await handle_cancelled_error()

                    except asyncio.TimeoutError as error:
                        try:
                            log_interrupt_error(error, self.debug)
                            self.connected = False
                            await asyncio.shield(asyncio.sleep(self.ping_timeout))
                            logging_reconnection(self.debug)
                            self.bi_directional_timeout = (
                                self.initial_bi_directional_timeout
                            )
                            continue
                        except asyncio.CancelledError:
                            await handle_cancelled_error()

                    except asyncio.CancelledError:
                        await handle_cancelled_error()

                    finally:
                        # Otherwise new tasks will be created which is a problem
                        try:
                            if not send_task.done():
                                send_task.cancel()
                            if not receive_task.done():
                                receive_task.cancel()
                        except Exception as error:
                            print("These tasks does not exist yet")

            except socket.gaierror as error:
                logging_gaieerror(error, self.retry_time, self.debug)
                await asyncio.sleep(self.retry_time)
                continue

            except ConnectionRefusedError as error:
                logging_connection_refused(error, self.retry_time, self.debug)
                await asyncio.sleep(self.retry_time)
                continue

            except Exception as error:
                log_interrupt_error(error, self.debug)

            finally:
                # Otherwise new tasks will be created which is a problem
                try:
                    if not send_task.done():
                        send_task.cancel()
                    if not receive_task.done():
                        receive_task.cancel()
                except Exception as error:
                    print("These tasks does not exist yet")

            if self.final_message_sent:
                logging_break(self.debug)
                break

        logging_api_completed(self.debug)

    def get_recordings_info_all(
        self, device_id: str = "mock-device-0", first_to_last=False
    ) -> list:
        recordings_url = f"{settings.REST_API_LOGIN}devices/{device_id}/recordings"
        if self.password == "":
            self.password = input("\nEnter your new password here: ")
        with requests.Session() as session:  # create a session (without auth?) and check the status? if status 200 ok i continue with the normal way
            result = session.get(
                recordings_url, auth=TokenAuth(token=self.password, auth_scheme='')
            )  # however ?
            if result.status_code == 200:
                print("Recording list retrieved successfully")
                recordings = result.json()
                recordings.sort(
                    key=lambda x: datetime.datetime.strptime(
                        x["status"]["startDeviceTimestamp"], ("%Y-%m-%dT%H:%M:%S.%f%z" if '.' in x["status"]["startDeviceTimestamp"] else "%Y-%m-%dT%H:%M:%S%z")
                    ),
                    reverse=first_to_last,
                )
                print(json.dumps(recordings, indent=4, sort_keys=True))
                return result.json()
            elif result.status_code == 401:
                print(f"Password for {device_id} is incorrect")
                return []
            elif result.status_code == 403:
                print(
                    "Wrong device ID, you can find the device ID in",
                    " the logs in the format XX-XX-XX-XX-XX-XX",
                )
                return []
            elif result.status_code == 412:
                print(
                    f"Device {device_id} is not registered",
                )
                return []
            elif result.status_code == 404:
                print(f"No recording found for device {device_id}")
                return []
            elif result.status_code == 502:
                print(f"Device {device_id} does not exist")
                return []
            else:
                print("Loading recording list failed")
                return []

    def get_recording_info_by_id(
        self, device_id: str, recording_id: str = "recordingId-0"
    ) -> list:
        recordings_url = f"{settings.REST_API_LOGIN}devices/{device_id}/recordings/{recording_id}"

        if self.password == "":
            self.password = input("\nEnter your new password here: ")
        with requests.Session() as session:
            result = session.get(recordings_url, auth=TokenAuth(token=self.password, auth_scheme=''))
            if result.status_code == 200:
                print("Recording ID file found")
                print(json.dumps(result.json(), indent=4, sort_keys=True))
                return result.json()
            elif result.status_code == 401:
                print(f"Password for {device_id} is incorrect")
                return []
            elif result.status_code == 403:
                print(
                    "Wrong device ID, you can find the device ID in",
                    " the logs in the format XX-XX-XX-XX-XX-XX",
                )
                return []
            elif result.status_code == 412:
                print(
                    f"Device {device_id} not registered",
                )
                return []
            elif result.status_code == 404:
                print(f"No recording found for {device_id} and {recording_id}")
                return []
            elif result.status_code == 502:
                print(f"Device {device_id} does not exits")
                return []
            else:
                print("Recording not found")
                print(result.status_code)
                print(result.json())
                return []

    def download_recording_by_id(
        self,
        device_id: str,
        recording_id: str = "recordingId-0",
    ) -> None:
        """Download the recording by ID and save it to the recordings folder"""

        recordings_folder_name = "recordings"
        recording_subfolder_name = recording_id

        if self.password == "":
            self.password = input("\nEnter your new password here: ")
        recording_types = ["eeg", "imu"]
        for data_type in recording_types:
            with requests.Session() as session:
                record_url_first = f"{settings.REST_API_LOGIN}devices/{device_id}/recordings/"
                record_url_second = f"{recording_id}/download/{data_type}"
                record_url = record_url_first + record_url_second
                result = session.get(record_url, auth=TokenAuth(token=self.password, auth_scheme=''))

                if result.status_code == 200:
                    print(f"Recording ID file found, downloading {data_type} data")
                    print(result.json())

                    # Creating folder for recording
                    folder_path = os.path.join(
                        recordings_folder_name, recording_subfolder_name
                    )
                    if not os.path.exists(folder_path):
                        os.makedirs(folder_path)

                    # get url from responsex
                    url = result.json()["downloadUrl"]
                    result = session.get(url)
                    filename = f"{recording_id}_{data_type}.csv"
                    file_path = os.path.join(folder_path, filename)

                    print(f"Writing to file: {file_path}")
                    with open(file_path, "wb") as file:
                        file.write(result.content)

                    print("Downloading complete for recording ID: ", recording_id)

                elif result.status_code == 401:
                    if data_type == "eeg":
                        print(f"Password for {device_id} is incorrect")

                elif result.status_code == 403:
                    if data_type == "eeg":
                        print(
                            "Wrong device ID, you can find the device ID in",
                            " the logs in the format XX-XX-XX-XX-XX-XX",
                        )
                elif result.status_code == 412:
                    if data_type == "eeg":
                        print(f"Device {device_id} is not registered")
                elif result.status_code == 404:
                    print(f"No {data_type} recording found for this device ID")
                elif result.status_code == 502:
                    if data_type == "eeg":
                        print(f"Device {device_id} does not exist")
                else:
                    if data_type == "eeg":
                        print("Data download failed")
                        print(result.status_code)
                        print(result.json())


@dataclass
class GuardianDataModel:
    """Data model for Guardian data"""

    deviceTimestamp: Union[str, None]
    deviceID: Union[str, None]
    recordingID: Union[str, None]
    payload: Union[str, None]  # This is a base64 encoded bytearray as a string
    impedance: Union[int, None]
    stop: Union[bool, None]
