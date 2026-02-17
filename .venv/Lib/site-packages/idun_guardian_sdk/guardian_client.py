"""
Initialization of the IDUN Guardian Client
"""

import asyncio
import logging
import os
from typing import Optional

from bleak import exc

from .constants import LOG_FORMAT
from .event_handlers import (
    LiveInsightsEvent,
    RealtimePredictionEvent,
    default_console_handler,
)
from .exceptions import APIRequestError
from .guardian_ble import GuardianBLE
from .guardian_http_api import GuardianHttpAPI
from .guardian_recording import GuardianRecording, Subscription
from .polling_service import PollingService
from .types import FileTypes
from .utils import check_ble_address

logger = logging.getLogger("idun_guardian_sdk")


class GuardianClient:
    """
    Main Class object for the user to interact with IDUN Guardian Earbuds and APIs

    All functional operations can be done through this class object: Device (Bluetooth) Operations, HTTP API, and Live Recording.
    """

    _ws_endpoint_url = "wss://ws-api.idun.cloud"
    _http_endpoint_url = "https://api.idun.cloud"

    def __init__(
        self,
        address: Optional[str] = None,
        ws_endpoint_url: Optional[str] = None,
        http_endpoint_url: Optional[str] = None,
        api_token: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        """
        Args:
            address (str, optional): The MAC address of the Guardian Earbuds.
            ws_endpoint_url (str, optional): The WebSocket endpoint URL. If not provided, the default URL is used.
            http_endpoint_url (str, optional): The HTTP endpoint URL. If not provided, the default URL is used.
            api_token (str, optional): The API token. Defaults to None. Required if any API call is needed.
            debug (bool, optional): Enable debug mode. Defaults to False.
        """
        self._polling_service = PollingService()
        self._configure_logger(debug)
        self.address = address
        self._api_token = api_token
        self._guardian_ble = None
        self._guardian_http_api = None
        self._guardian_recording = None

        if ws_endpoint_url is not None:
            self._ws_endpoint_url = ws_endpoint_url

        if http_endpoint_url is not None:
            self._http_endpoint_url = http_endpoint_url

    @property
    def api_token(self):
        """
        Lazy loading of the API token
        """
        # If not provided during initialization, check the environment variable
        if not self._api_token:
            self._api_token = os.environ.get("IDUN_API_TOKEN")

        if self._api_token is None:
            raise ValueError("API token is not provided. Please provide an API token.")

        return self._api_token

    @property
    def guardian_ble(self):
        """
        Lazy loading of the GuardianBLE object
        """
        if self._guardian_ble is None:
            if self.address:
                check_ble_address(self.address)
            self._guardian_ble = GuardianBLE(self.address)
        return self._guardian_ble

    @property
    def guardian_http_api(self):
        """
        Lazy loading of the GuardianHttpAPI object
        """
        if self._guardian_http_api is None:
            self._guardian_http_api = GuardianHttpAPI(self._http_endpoint_url, self.api_token)
        return self._guardian_http_api

    @property
    def guardian_recording(self):
        """
        Lazy loading of the GuardianRecording object
        """
        if self._guardian_recording is None:
            self._guardian_recording = GuardianRecording(ws_url=self._ws_endpoint_url, api_token=self.api_token)
        return self._guardian_recording

    def _configure_logger(self, debug):
        """Configure the logger for the Guardian Client"""
        log_level = logging.DEBUG if debug else logging.INFO
        logger.propagate = False

        formatter = logging.Formatter(LOG_FORMAT)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(log_level)

        logger.setLevel(log_level)
        logger.addHandler(stream_handler)

    def _end_ongoing_recordings(self):
        """
        Get recordings with status ONGOING and NOT_STARTED and end them
        """
        logger.debug("[CLIENT]: Ending ongoing recordings if any")
        recs = []
        recs.extend(self.get_recordings(status="ONGOING").get("items", []))
        recs.extend(self.get_recordings(status="NOT_STARTED").get("items", []))

        for rec in recs:
            self.end_recording(rec["recordingId"])

    # ------------------ BLE section ------------------
    async def search_device(self):
        """Search for the Guardian Earbuds device and return the address

        Returns:
            str: Address of the device
        """
        address = await GuardianBLE.search_device()
        return address

    async def get_device_mac_address(self) -> str:
        """Get the MAC address of the Guardian Earbuds.
        It searches the MAC address of the device automatically. This
        address is used as the deviceID for cloud communication
        """
        await self.guardian_ble.connect_device()
        device_address = await self.guardian_ble.get_device_mac()
        return device_address

    async def connect_device(self):
        """
        Bluetooth connect to the Guardian Earbuds device

        Device connection is automatically handled by the SDK.
        You can call this method to connect to the device as needed.
        """
        await self.guardian_ble.connect_device()

    async def disconnect_device(self):
        """
        Bluetooth disconnect the Guardian Earbuds device

        Device disconnection is automatically handled by the SDK on program exit.
        You can call this method to disconnect to the device as needed.
        """
        await self.guardian_ble.disconnect_device()

    async def check_battery(self):
        """
        Reads and print the battery level of the device
        """
        return await self.guardian_ble.read_battery_level()

    async def stream_impedance(self, mains_freq_60hz: bool = False, handler: Optional[callable] = None):
        """
        Stream impedance data from the Guardian Earbuds

        Args:
            mains_freq_60hz (bool, optional): Set to True if the mains frequency is 60Hz. Defaults to False.
            handler (callable, optional): The callback function to handle the impedance data
        """
        await self.guardian_ble.stream_impedance(mains_freq_60hz=mains_freq_60hz, handler=handler)

    def stop_impedance(self):
        """
        Stops impedance streaming
        """
        if not self.guardian_ble.run_impedance:
            logger.info("[CLIENT]: Impedance streaming is not running. Nothing to do")
            return
        self.guardian_ble.run_impedance = False

    # ------------------ Live Recording section ------------------
    def subscribe_live_insights(
        self,
        raw_eeg: bool = False,
        filtered_eeg: bool = False,
        imu: bool = False,
        handler: callable = default_console_handler,
    ):
        """
        Subscribe for live insights from the Guardian Earbuds. One of the optional flags
        must be set to True.

        Args:
            raw_eeg (bool, optional): Subscribe for Raw EEG data. Defaults to False.
            filtered_eeg (bool, optional): Subscribe for Filtered EEG data. Defaults to False.
            imu (bool, optional): Subscribe for IMU data. Defaults to False.
            handler: The callback function to handle the live insights data

        Raises:
            ValueError: If none of the optional flags are set to True
        """
        stream_types = []
        if raw_eeg:
            stream_types.append("RAW_EEG")
        if filtered_eeg:
            stream_types.append("FILTERED_EEG")
        if imu:
            stream_types.append("IMU")

        if len(stream_types) == 0:
            raise ValueError("At least one stream type must be selected: raw_eeg=True | fileterd_eeg=True | imu=True")

        self.guardian_recording.msg_handler.subscribe(LiveInsightsEvent, handler)
        subs = Subscription(identifiers=stream_types, event_type=LiveInsightsEvent)
        self.guardian_recording.ws_subscriptions.append(subs)

    def subscribe_realtime_predictions(
        self,
        fft: bool = False,
        jaw_clench: bool = False,
        bin_heog: bool = False,
        quality_score: bool = False,
        calm_score: bool = False,
        handler: callable = default_console_handler,
    ):
        """
        Subscribe for real-time predictions from the Guardian Earbuds. One of the optional flags
        must be set to True.

        Args:
            fft (bool, optional): Subscribe for FFT data. Defaults to False.
            jaw_clench (bool, optional): Subscribe for Jaw Clench data. Defaults to False.
            bin_heog (bool, optional): Subscribe for BIN_HEOG data. Defaults to False.
            quality_score (bool, optional): Subscribe for Quality Score data. Defaults to False.
            calm_score (bool, optional): Subscribe for Calm Score data. Defaults to False.
            handler: The callback function to handle the real-time predictions data

        Raises:
            ValueError: If none of the optional flags are set to True
        """
        predictions = []
        if fft:
            predictions.append("FFT")
        if jaw_clench:
            predictions.append("JAW_CLENCH")
        if bin_heog:
            predictions.append("BIN_HEOG")
        if quality_score:
            predictions.append("QUALITY_SCORE")
        if calm_score:
            predictions.append("CALM_SCORE")

        if len(predictions) == 0:
            raise ValueError("At least one stream type must be selected: fft=True | jaw_clench=True | bin_heog=True")

        self.guardian_recording.msg_handler.subscribe(RealtimePredictionEvent, handler)
        subs = Subscription(identifiers=predictions, event_type=RealtimePredictionEvent)
        self.guardian_recording.ws_subscriptions.append(subs)

    async def start_recording(
        self,
        recording_timer: int = 36000,
        led_sleep: bool = False,
        calc_latency: bool = False,
    ):
        """
        Start recording data from the Guardian Earbuds.
        Bidirectional websocket connection to the Guardian Cloud API.
        The recording keeps running until the recording_timer is reached or the user manually
        stops the recording by gracefully interrupting the recording with Ctrl + C

        Args:
            recording_timer (int, optional): The duration of the recording in seconds. Defaults to 36000.
            led_sleep (bool, optional): Enable LED sleep mode. Defaults to False.
            calc_latency (bool): Enables calculation and printing data transmission latency to the cloud. Defaults to False.

        Returns:
            str: Recording ID

        Raises:
            ValueError: For wrong Device ID
        """
        # Ending ongoing recordings if any
        self._end_ongoing_recordings()

        # Making sure guardian_ble has connection_handler task started
        self.guardian_ble._start_connection_handler()

        # Set/resetting guardian_recording flags
        self.guardian_recording.set_init_recording()
        task_list = []
        try:
            logger.info("[CLIENT]: Starting recording")
            logger.info(f"[CLIENT]: Recording timer: {recording_timer} seconds")

            await self.guardian_ble.connect_device()
            self.guardian_recording.device_id = self.guardian_ble.mac_id

            logger.info("[CLIENT]: Ensuring hardware version is synced with Cloud")
            await self.ensure_hardware_version_synced()

            logger.debug("[CLIENT]: Validating if API Device ID matches with BLE Device ID")
            api_device_id = self.get_user_info().get("device_id")
            if not api_device_id:
                raise ValueError("Failed to get Device ID from the API")
            if api_device_id != self.guardian_recording.device_id:
                raise ValueError(
                    f"API device ID {api_device_id} does not match with BLE device ID {self.guardian_recording.device_id}"
                )
            else:
                logger.debug("[CLIENT]: Validation passed: API Device ID matches with BLE Device ID")

            task_list.extend(
                [
                    asyncio.create_task(
                        self.guardian_ble.run_ble_record(
                            self.guardian_recording, recording_timer, led_sleep, calc_latency
                        )
                    ),
                    asyncio.create_task(self.guardian_recording.start_streaming(calc_latency)),
                ]
            )

            await asyncio.gather(*task_list)

        except exc.BleakError as err:
            logger.error("[CLIENT]: BLE error: %s", err)
        except asyncio.exceptions.CancelledError:
            logger.debug("[CLIENT]: Keyboard interrupt received, terminating tasks")
        finally:
            # Ensure all tasks are awaited
            for task in task_list:
                if not task.done():
                    await task
        logger.info("[CLIENT]: Recording Finished")
        logger.debug("[CLIENT]: -----------  All tasks are COMPLETED -----------")
        logger.info(f"[CLIENT]: Recording ID {self.guardian_recording.recording_id}")

        return self.guardian_recording.recording_id

    def get_recording_id(self):
        """
        Gets the ID of current recording.

        Raises: ValueError: If the recording ID is not available
        """
        if not self.guardian_recording.recording_id:
            raise ValueError("Recording ID is not yet available. Recording is not started.")
        return self.guardian_recording.recording_id

    # ------------------ HTTP API section ------------------
    def download_file(self, recording_id: str, file_type: FileTypes, file_path: Optional[str] = None):
        """
        Download a file from a recording. Possible file types are: EEG, IMU, IMPEDANCE

        Args:
            recording_id (str): the id of the recording
            file_type (FileTypes): the type of file to download
            file_path (str, optional): where to save the file
        """
        url = self.guardian_http_api.download_recording(recording_id=recording_id, file_type=file_type)
        self.guardian_http_api.save_file_from_s3(url, file_path)

    def get_recordings(self, limit=200, status: Optional[str] = None, page_index: Optional[int] = None):
        """
        Retrieves recordings from the Guardian HTTP API.

        Args:
            limit (int, optional): The maximum number of recordings to retrieve. Defaults to 200.
            status (str, optional): The status of the recordings to retrieve. Defaults to None.
                Status options are:
                - NOT_STARTED - Status for a recording when a "start recording" signal is sent, but no data has been sent yet.
                - ONGOING - This is the state of a recording when the data are still incoming.
                - PROCESSING - When the API receives a "stop recording signal", the recording status is set to processing.
                - COMPLETED - When the recording has been successfully finished and saved.
                - FAILED - If the recording failed.
            page_index (int, optional): The index of the page to retrieve. Defaults to None.

        Returns:
            list: A list of recordings retrieved from the Guardian HTTP API.
        """
        return self.guardian_http_api.get_recordings(limit, status, page_index)

    def delete_recording(self, recording_id: str):
        """
        Deletes a recording from the Guardian HTTP API.

        Args:
            recording_id (str): The ID of the recording to delete.
        """
        return self.guardian_http_api.delete_recording(recording_id)

    def end_recording(self, recording_id: str):
        """
        Ends a recording from the Guardian HTTP API.

        Args:
            recording_id (str): The ID of the recording to end.
        """
        return self.guardian_http_api.end_recording(recording_id)

    def update_recording_tags(self, recording_id, tags):
        """
        Updates the tags of a recording from the Guardian HTTP API.

        Args:
            recording_id (str): The ID of the recording to update.
            tags (list): The list of tags to update.
        """
        return self.guardian_http_api.update_recording_tags(recording_id, tags)

    def update_recording_display_name(self, recording_id: str, display_name: str):
        """
        Updates the display name of a recording from the Guardian HTTP API.

        Args:
            recording_id (str): The ID of the recording to update.
            display_name (str): The new display name.
        """
        return self.guardian_http_api.update_recording_display_name(recording_id, display_name)

    def generate_and_download_sleep_report(self, recording_id: str, file_path: Optional[str] = None):
        """
        Generates and downloads a sleep report for a recording from the Guardian HTTP API.

        Args:
            recording_id (str): The ID of the recording to generate the sleep report for.
            file_path (str, optional): The path to save the sleep report to. Defaults to None.
        """
        report_id = self.guardian_http_api.generate_sleep_report(recording_id)
        try:
            logger.info("[CLIENT]: Waiting for the report to be ready...")
            url = self._polling_service.poll_until_ready(
                self.guardian_http_api.download_sleep_report_by_id, report_id=report_id
            )
        except Exception as e:
            raise APIRequestError(
                f"Failed to download sleep report ({report_id}) for recording {recording_id}. {str(e)}"
            )

        saved_path = self.guardian_http_api.save_file_from_s3(url, file_path)
        logger.info(f"[CLIENT]: Sleep report downloaded successfully at: {saved_path}")

    def download_sleep_report_raw_data(self, recording_id: str, file_path: Optional[str] = None):
        """
        Downloads the sleep report raw data for a recording.

        Args:
            recording_id (str): The ID of the recording to download the sleep report raw data.
        """
        res = self.guardian_http_api.download_sleep_report_raw_data(recording_id)
        saved_path = self.guardian_http_api.save_file_from_s3(res.url, file_path)
        logger.info(f"[CLIENT]: Sleep report raw data downloaded successfully at: {saved_path}")

    def generate_and_download_daytime_report(self, recording_id: str, file_path: Optional[str] = None):
        """
        Generates and downloads a daytime report for a recording from the Guardian HTTP API.

        Args:
            recording_id (str): The ID of the recording to generate the daytime report for.
            file_path (str, optional): The path to save the daytime report to. Defaults to None.
        """
        report_id = self.guardian_http_api.generate_daytime_report(recording_id)
        logger.info("[CLIENT]: Waiting for the report to be ready...")
        try:
            url = self._polling_service.poll_until_ready(
                self.guardian_http_api.download_daytime_report_by_id, report_id=report_id
            )
        except Exception as e:
            raise APIRequestError(f"Failed to generate daytime report for recording {recording_id}. {str(e)}")

        saved_path = self.guardian_http_api.save_file_from_s3(url, file_path)
        logger.info(f"[CLIENT]: Daytime report downloaded successfully at: {saved_path}")

    def download_daytime_report_raw_data(self, recording_id: str, file_path: Optional[str] = None):
        """
        Downloads the daytime report raw data for a recording.

        Args:
            recording_id (str): The ID of the recording to download the daytime report raw data.
        """
        res = self.guardian_http_api.download_daytime_report_raw_data(recording_id)
        saved_path = self.guardian_http_api.save_file_from_s3(res.url, file_path)
        logger.info(f"[CLIENT]: Daytime report raw data downloaded successfully at: {saved_path}")

    def get_recording_reports(self, recording_id: str):
        """
        Get the list of reports for a recording from the Guardian HTTP API

        Args:
            recording_id (str): The id of the recording.

        Returns:
            list: the reports for the recording
        """
        return self.guardian_http_api.get_recording_reports(recording_id)

    def get_user_info(self):
        """
        Get the user information from the Guardian HTTP API, depending on the API token provided.

        Returns:
            dict: A dictionary containing the following keys:
                - 'idun_id': The IDUN ID of the user.
                - 'device_id': The device ID of the user.
        """
        return self.guardian_http_api.get_user_info()

    def generate_brain_art(self, recording_id, calm_score):
        """
        Generate a brain art for a recording.
        """
        return self.guardian_http_api.generate_brain_art(recording_id, calm_score)

    async def ensure_hardware_version_synced(self):
        """
        Ensure the hardware version is synchronized with the Cloud before recording.

        This method:
        1. Gets the user information from the Cloud
        2. If the hardware_version already exists in the Cloud, skip the upload
        3. If no hardware_version exists, gets hardware version from the connected device via BLE
        4. Uploads the hardware version to the Cloud

        This should be called before starting any recording to ensure the Cloud
        has the correct hardware version information.

        Returns:
            None: Method completes when hardware version is ensured to be synced
        """
        user_info = self.guardian_http_api.get_user_info()

        if user_info.get("hardware_version"):
            logger.info("[CLIENT]: Hardware version already exists in the Cloud")
            return

        hardware_version = await self.guardian_ble.get_device_hardware_version()
        logger.info(f"[CLIENT]: Retrieved hardware version: {hardware_version}")

        if not self.guardian_http_api.upload_hardware_version(hardware_version):
            raise ValueError("Failed to upload hardware version to the Cloud")
        logger.info("[CLIENT]: Hardware version uploaded successfully")

        return
