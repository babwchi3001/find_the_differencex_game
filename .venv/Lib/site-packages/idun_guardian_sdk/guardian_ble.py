"""
Guardian Bluetooth utils.
"""

import asyncio
import base64
import datetime
import gc
import logging
import platform
import time
import typing
from codecs import utf_8_encode

from bleak import BleakClient, BleakScanner, exc

from .debug_logs import *
from .guardian_recording import GuardianRecording
from .utils import now
from .websocket_messages import PublishRawMeasurements, EndOngoingRecording

SEARCH_BREAK = 3

UUID_MEAS_EEGIMU: str = "beffd56c-c915-48f5-930d-4c1feee0fcc4"
UUID_MEAS_IMP: str = "beffd56c-c915-48f5-930d-4c1feee0fcc8"
UUID_DEVICE_SERVICE: str = "0000180a-0000-1000-8000-00805f9b34fb"
UUID_MAC_ID: str = "00002a25-0000-1000-8000-00805f9b34fb"
UUID_FIRMWARE_VERSION: str = "00002a26-0000-1000-8000-00805f9b34fb"
UUID_HARDWARE_VERSION: str = "00002a27-0000-1000-8000-00805f9b34fb"
UUID_CFG: str = "beffd56c-c915-48f5-930d-4c1feee0fcc9"
UUID_CMD: str = "beffd56c-c915-48f5-930d-4c1feee0fcca"
LED_ON_CFG: str = "d1"
LED_OFF_CFG: str = "d0"
NOTCH_FREQ_50_CFG: str = "n0"
NOTCH_FREQ_60_CFG: str = "n1"
START_CMD: str = "M"  #'\x62' #b -> start measurement
STOP_CMD: str = "S"  # '\x73' #s -> stop measurement
START_IMP_CMD: str = "Z"  # '\x7a' #z -> start impedance
STOP_IMP_CMD: str = "X"  # '\x78' #x -> stop impedance
UUID_BATT_GDK: str = "00002a19-0000-1000-8000-00805f9b34fb"

logger = logging.getLogger("idun_guardian_sdk")


class GuardianBLE:
    """Main Guardian BLE client."""

    def __init__(self, address: str = "") -> None:
        """Initialize the Guardian BLE client.

        Args:
            address (str, optional): BLE device address. Defaults to "".
        """
        self.client: typing.Optional[BleakClient] = None

        self.address = address

        # Initial connection flags
        self.connect_ble: bool = False  # Flag to control when the device should be connected or not
        self.connection_established: bool = False
        self.connection_event = None  # Event to trigger the connection handler
        self.initial_time = True
        self._connection_handler_task = None

        self.original_time = time.time()
        self.ble_delay = 1

        # The timing constants
        self.sample_rate = 250
        self.amount_samples_packet = 20
        self.max_index = 256
        self.prev_index = 0
        self.prev_timestamp = 0
        self.sequence_number = 0

        self.remaining_time = 1

        self.mac_id = ""
        self.platform = platform.system()

        self.run_recording = False
        self.run_impedance = False
        self._start_connection_handler()

        self.char_eeg_imu = UUID_MEAS_EEGIMU
        self.uuid_config = UUID_CFG

    async def _wait_connect_flag_sync(self):
        """
        Waits for the connect and connection_established flag to be sync
        """
        while True:
            if self.connect_ble == self.connection_established:
                break
            await asyncio.sleep(1)

    async def connect_device(self):
        """
        Connects the device

        Sets the connect_ble flag to True and waits for the connection to be
        established by the connection handler

        Do nothing if the device is already connected
        """
        self._start_connection_handler()
        if self.connect_ble and self.connection_established:
            return
        self.connect_ble = True
        self.connection_event.set()  # Trigger the event for connection handler task
        await self._wait_connect_flag_sync()

    async def disconnect_device(self):
        """
        Disconnects the device

        Sets the connect_ble flag to False and waits for the connection to be
        established by the connection handler

        Do nothing if the device is already disconnected
        """
        if not self.connect_ble and not self.connection_established:
            return
        self.connect_ble = False
        self.connection_event.set()  # Trigger the event for connection handler task
        await self._wait_connect_flag_sync()

    async def _connection_handler(self):
        """
        Handles the device connection/disconnection
        """
        logger.debug("[BLE]: Connection handler started.")
        while True:
            try:
                await self.connection_event.wait()
                self.connection_event.clear()
                if self.connect_ble and not self.connection_established:
                    logger.debug("[BLE]: Connecting to the device...")
                    while not self.connection_established:
                        await self.connect_to_device()
                if not self.connect_ble and self.connection_established:
                    logger.debug("[BLE]: Disconnecting from the device...")
                    await self.client.disconnect()
                    self.connection_established = False
                await asyncio.sleep(1)
            except asyncio.CancelledError:  # On program exit or cancel command
                logger.debug("[BLE]: Connection handler gracefully stopping.")
                if self.client is not None and self.client.is_connected:
                    logger.debug("[BLE]: Disconnecting from the device on handler stop...")
                    try:
                        await self.client.disconnect()
                        self.connection_established = False
                        self.connect_ble = False
                        gc.collect()
                    except Exception:
                        log_exception_in_disconnecting()
                break
        self.connection_event = None

    def _start_connection_handler(self):
        """
        Start the connection handler task if it's not running
        """
        if not self.connection_event:
            self.connection_event = asyncio.Event()  # Event to trigger the connection handler
        if self._connection_handler_task is None or self._connection_handler_task.done():
            logger.debug("[BLE]: Starting connection handler task.")
            self._connection_handler_task = asyncio.create_task(self._connection_handler())

    def _disconnected_callback(self, client):
        """
        Callback function when device is disconnected.

        Args:
            client (BleakClient): BleakClient object
        """
        logging_disconnected_recognised()
        self.connection_established = False

    async def get_device_mac(self) -> str:
        """
        Get the device MAC address. Device must be already connected
        This is different from BLE device address
        (UUID on Mac or MAC address on Windows)

        Returns:
            str: MAC address
        """
        logging_searching()
        value = bytes(await self.client.read_gatt_char(UUID_MAC_ID))
        await asyncio.sleep(self.ble_delay)
        firmware_version = bytes(await self.client.read_gatt_char(UUID_FIRMWARE_VERSION))
        mac_address = value.decode("utf-8")
        firmware_decoded = firmware_version.decode("utf-8")
        mac_address = mac_address.replace(":", "-")

        logging_device_info(mac_address, firmware_decoded)
        return mac_address

    @staticmethod
    async def search_device() -> str:
        """This function searches for the device and returns the address of the device.
        If the device is not found, it exits the program. If multiple devices are found,
        it asks the user to select the device. If one device is found, it returns the
        address of the device.

        Returns:
            str: Device address
        """

        while True:
            ble_device_list: list = []
            devices = await BleakScanner.discover()
            ige_prefix = "IGE"  # "IGEB" for 2.1a, "IGE-XXXXXX" for 3.0a
            print("\n----- Available devices -----\n")
            print("Index | Name | Address")
            print("----------------------------")
            device_idx = 0
            for device in devices:
                # print device discovered
                if device.name and str(device.name).startswith(ige_prefix):
                    print(f"{device_idx}     | {device.name} | {device.address}")
                    ble_device_list.append(device.address)
                    device_idx += 1
            print("----------------------------\n")

            if len(ble_device_list) == 0:
                logging_device_not_found(SEARCH_BREAK)
                await asyncio.sleep(SEARCH_BREAK)

            elif len(ble_device_list) == 1:
                logging_device_found(ble_device_list)
                address = ble_device_list[0]
                break
            else:
                index_str = input(
                    "Enter the index of the GDK device you want to connect to \
                    \nIf cannot find the device, please restart the program and try again: "
                )
                index = int(index_str)
                address = ble_device_list[index]
                break

        logger.info("[BLE]: Selected address %s", address)

        return address

    async def connect_to_device(self):
        """
        This function initialises the connection to the device.
        It finds the device using the address, sets up callback,
        and connects to the device.
        """
        if not self.address:
            logger.info("Device address not provided, searching for the device...")
            self.address = await self.search_device()
        logging_trying_to_connect(self.address)

        device = await BleakScanner.find_device_by_address(self.address, timeout=20.0)
        if not device:
            raise exc.BleakError(f"A device with address {self.address} could not be found.")

        if self.platform == "Windows":
            if not self.client:
                self.client = BleakClient(device, disconnected_callback=self._disconnected_callback)
        else:
            self.client = None
            self.client = BleakClient(device, disconnected_callback=self._disconnected_callback)
        if self.client is not None:
            try:
                await asyncio.wait_for(self.client.connect(), timeout=4)
            except asyncio.TimeoutError:
                log_timeout_while_trying_connection()
                pass
            except Exception as err:
                log_exception_while_trying_connection(err)
                pass
            if self.client.is_connected:
                if self.mac_id == "":
                    try:
                        self.mac_id = await self.get_device_mac()

                    except Exception as err:
                        log_exception_unable_to_find_MACaddress(err)
                        self.connection_established = False
                        return 0
                if self.mac_id:
                    self.connection_established = True
                    logging_connected(self.address)
                    return 1

            else:
                logger.debug("[BLE]: No Connection has been established, will disconnect and try to reconnect again")
                try:
                    await asyncio.sleep(4)
                except Exception:
                    log_exception_in_disconnecting()
                gc.collect()
                self.connection_established = False
                return 0
        else:
            log_not_client_found()

    async def run_ble_record(
        self,
        guardian_recording: GuardianRecording,
        record_time: int = 60,
        led_sleep: bool = False,
        calc_latency: bool = False,
    ) -> None:
        """
        This function runs the recording of the data. It sets up the bluetooth
        connection, starts the recording, and then reads the data and adds it to
        the GuardianRecording's data queue.

        Args:
            guardian_recording (GuardianRecording): GuardianRecording object
            record_time (_type_): The time to record for
            led_sleep (_type_): Whether to turn off the LED
            calc_latency (bool): Enables calculation and display of data transmission latency to the cloud. Defaults to False.

        Raises:
            BleakError: _description_
        """

        def time_stamp_creator(new_index):
            """
            This function creates a timestamp for the cloud based on the
            time the recording started. Each time stamp is based on the index
            of that is sent from the device. The index is the number of iterates
            between 0 and 256. The time stamp is the 1/250s multiplied by the
            index.

            Args:
                new_index (int): Index of the data point from the ble packet

            Returns:
                str: Timestamp in the format of YYYY-MM-DDTHH:MM:SS
            """
            index_diff = new_index - self.prev_index

            if self.prev_timestamp == 0:
                time_data = datetime.datetime.now().astimezone().isoformat()
                # convert time_data to a float in seconds
                time_data = time.mktime(datetime.datetime.strptime(time_data, "%Y-%m-%dT%H:%M:%S.%f%z").timetuple())
                new_time_stamp = time_data
            else:
                multiplier = (index_diff + self.max_index) % self.max_index
                new_time_stamp = (
                    self.amount_samples_packet * (1 / self.sample_rate) * multiplier
                ) + self.prev_timestamp

            self.prev_index = new_index
            self.prev_timestamp = new_time_stamp

            return new_time_stamp * 1000

        async def data_handler(_, data):
            """Data handler for the BLE client.
                Data is put in a queue and forwarded to the GuardianRecording.

            Args:
                callback (handler Object): Handler object
                data (bytes): Binary data package
            """
            data_base_64 = base64.b64encode(data).decode("ascii")
            new_time_stamp = time_stamp_creator(data[1])

            package = PublishRawMeasurements(
                event=data_base_64,
                deviceId=self.mac_id,
                deviceTs=new_time_stamp,
                recordingId=guardian_recording.recording_id,
                sequence=self.sequence_number,
            ).to_dict()
            if calc_latency:
                guardian_recording.latency_map[self.sequence_number] = time.time()
            self.sequence_number += 1
            if not guardian_recording.data_queue.full():
                await asyncio.shield(guardian_recording.data_queue.put(package))
            else:
                msg = await asyncio.shield(guardian_recording.data_queue.get())
                logger.debug("data_queue is full discarding: ", msg)
                await asyncio.shield(guardian_recording.data_queue.put(package))

        async def wait_recording_id_set():
            """Wait for the recording ID to be set by the GuardianRecording."""
            while not (guardian_recording.rec_started and guardian_recording.recording_id):
                logger.debug("[BLE]: Waiting recording id to be set by GuardianRecording")
                await asyncio.sleep(1)
            logger.debug(f"[BLE]: Recording ID Set: {guardian_recording.recording_id}")

        async def send_start_commands_recording():
            """Send start commands to the device."""
            logging_sending_start()

            # ------------------ Configuration ------------------
            if led_sleep:
                await asyncio.sleep(self.ble_delay)
                await self.client.write_gatt_char(UUID_CFG, utf_8_encode(LED_OFF_CFG)[0])
            # ------------------ Subscribe to notifications ------------------
            # Notify the client that these two services are required
            logging_subscribing_eeg_notification()
            await asyncio.sleep(self.ble_delay)
            await self.client.start_notify(self.char_eeg_imu, data_handler)

            # ------------------ Start commands ------------------
            # sleep so that client can respond
            await asyncio.sleep(self.ble_delay)
            # send start command for recording data
            await self.client.write_gatt_char(UUID_CMD, utf_8_encode(START_CMD)[0])

        async def stop_recording_script(load_final_pkg=False):
            # ------------------ Send stop EEG recording command ------------------
            logger.debug("[BLE]: Sending stop command to device")
            try:
                await asyncio.sleep(self.ble_delay)
                await self.client.write_gatt_char(UUID_CMD, utf_8_encode(STOP_CMD)[0])
                await asyncio.sleep(self.ble_delay)
                await self.client.stop_notify(self.char_eeg_imu)
            except:
                logger.debug(f"[BLE]: Notification was already stopped")

            # ------------------ Load end recording package into the queue ------------------
            if load_final_pkg:
                package = EndOngoingRecording(self.mac_id, guardian_recording.recording_id, now()).to_dict()
                if not guardian_recording.data_queue.full():
                    await guardian_recording.data_queue.put(package)
                else:
                    await guardian_recording.data_queue.get()
                    await guardian_recording.data_queue.put(package)
                logger.debug("[BLE]: EndOnGoingRecording package loaded into data queue for GuardianRecording")
            await asyncio.sleep(self.ble_delay)

            # ------------------ Configuring LED back on ------------------
            if led_sleep:
                logging_turn_led_on()
                await asyncio.sleep(self.ble_delay)
                await self.client.write_gatt_char(UUID_CFG, utf_8_encode(LED_ON_CFG)[0])

            await asyncio.sleep(self.ble_delay)
            logger.debug("[BLE]: Recording successfully stopped")

        def initialise_timestamps():
            if self.initial_time:
                self.initial_time = False  # record that this is the initial time
                self.original_time = time.time()

        async def main_loop():
            while True:
                if self.connection_established and self.run_recording:
                    await asyncio.shield(asyncio.sleep(self.ble_delay))
                    self.remaining_time = max(0, record_time - (time.time() - self.original_time))
                    logger.debug(f"[BLE]: Time left: {round(self.remaining_time)}s")
                    if self.remaining_time <= 0:
                        break
                else:
                    break

        # >>>>>>>>>>>>>>>>>>>>> Start of recording process <<<<<<<<<<<<<<<<<<<<<<<<
        # ------------------ Initialise values for timestamps ------------------
        self.prev_timestamp = 0
        self.prev_index = -1
        # ------------------ Initialise time values for recording timeout ------------------
        # This has been decoupled from the device timing for robustness
        self.original_time = time.time()
        self.initial_time = True

        self.run_recording = True

        while self.run_recording:
            logger.debug(f"[BLE]: Connection Established: {self.connection_established}")

            try:
                await self.connect_device()
                if self.client is not None:
                    if self.client.is_connected:
                        logger.debug("[BLE]: Device is connected")

                    # Waiting recording Id to be set by GuardianRecording
                    await asyncio.wait_for(wait_recording_id_set(), timeout=20)  # TODO: set better/configurable timeout

                    await send_start_commands_recording()
                    logger.debug("[BLE]: Recording successfully started")

                    # >>>>>>>>>>>>>>>>>>>>> Main loop <<<<<<<<<<<<<<<<<<<<<<<<
                    initialise_timestamps()
                    await asyncio.shield(main_loop())
                    # >>>>>>>>>>>>>>>>>>>>> Main loop <<<<<<<<<<<<<<<<<<<<<<<<

                if self.remaining_time <= 0:
                    logger.debug(
                        f"[BLE]: Recording time reached. Time run: {round(time.time() - self.original_time, 2)}",
                    )
                    await stop_recording_script(load_final_pkg=True)
                    self.run_recording = False
                    break

            except asyncio.CancelledError:
                logger.debug("[BLE]: KeyboardInterrupt applied, terminating...")
                if self.run_recording:
                    self.run_recording = False
                    await stop_recording_script()
                break

        logging_ble_complete()

    async def get_device_hardware_version(self) -> str:
        """
        Get the device hardware version.

        Returns:
            str: Hardware version string
        """
        await self.connect_device()
        logger.debug("[BLE]: Reading hardware version")
        try:
            hardware_version = bytes(await self.client.read_gatt_char(UUID_HARDWARE_VERSION))
            hardware_version_decoded = hardware_version.decode("utf-8")
            logger.debug("[BLE]: Hardware version: %s", hardware_version_decoded)
            return hardware_version_decoded
        except exc.BleakError as err:
            logger.error("[BLE]: Error reading hardware version: %s", err)
            raise

    async def read_battery_level(self) -> None:
        """Read the battery level of the device given pre-defined interval."""
        await self.connect_device()
        logger.debug("[BLE]: Reading battery level")
        try:
            value = int.from_bytes(
                (await self.client.read_gatt_char(UUID_BATT_GDK)),
                byteorder="little",
            )
            logger.debug("[BLE]: Battery level: %s%%", value)
            return value

        except exc.BleakError as err:
            logger.error("[BLE]: Error reading battery level: %s", err)
            await asyncio.sleep(1)

    async def stream_impedance(self, mains_freq_60hz: bool = False, handler: typing.Optional[callable] = None):
        """
        Stream impedance data from the Guardian Earbuds. Runs indefinitely until cancelled.

        Args:
            mains_freq_60hz (bool, optional): Set to True if the mains frequency is 60Hz. Defaults to False.
            handler: The callback function to handle the impedance data. If None is given, the default handler will be used.
                which simply logs the impedance value to the console.
        """

        def default_impedance_handler(data_int):
            logger.info(f"[BLE]: Impedance value : {round(data_int/1000,2)} kOhms")

        async def impedance_handler(_, data):
            """Impedance handler for the BLE client.

            Args:
                callback (handler Object): Handler object
                data (bytes): Binary data package with impedance values
            """
            data_int = int.from_bytes(data, byteorder="little")
            if handler is not None:
                handler(data_int)
            else:
                default_impedance_handler(data_int)

        async def send_start_commands_impedance():
            # ----------------- Configuration -----------------
            if mains_freq_60hz:
                await self.client.write_gatt_char(UUID_CFG, utf_8_encode(NOTCH_FREQ_60_CFG)[0])
            else:
                await self.client.write_gatt_char(UUID_CFG, utf_8_encode(NOTCH_FREQ_60_CFG)[0])

            # ----------------- Subscribe -----------------
            logger.debug("[BLE]: Subscribing impedance measurement")
            await asyncio.sleep(self.ble_delay)
            await self.client.start_notify(UUID_MEAS_IMP, impedance_handler)

            # ----------------- Send start command -----------------
            logger.debug("[BLE]: Sending start impedance commands")
            await asyncio.sleep(self.ble_delay)
            await self.client.write_gatt_char(UUID_CMD, utf_8_encode(START_IMP_CMD)[0])

        async def send_stop_command_impedance():
            # ------------------ Send stop impedance command ------------------
            logger.debug("[BLE]: Sending stop impedance command to device")
            try:
                await self.client.write_gatt_char(UUID_CMD, utf_8_encode(STOP_IMP_CMD)[0])
                await asyncio.sleep(self.ble_delay)
                await self.client.stop_notify(UUID_MEAS_IMP)
                await asyncio.sleep(self.ble_delay)
            except:
                logger.debug(f"[BLE]: Notification was already stopped")

        async def main_loop():
            while True:
                if self.connection_established and self.run_impedance:
                    await asyncio.shield(asyncio.sleep(self.ble_delay))
                else:
                    break

        # Sets run impedance to True and runs until cancelled or flag is set to False
        self.run_impedance = True

        while self.run_impedance:
            logger.debug(f"[BLE]: Connection Established: {self.connection_established}")

            try:
                await self.connect_device()
                if self.client is not None:
                    if self.client.is_connected:
                        logger.debug("[BLE]: Device is connected")

                    await send_start_commands_impedance()
                    logger.info("[BLE]: Impedance measurement successfully started")

                    # >>>>>>>>>>>>>>>>>>>>> Main loop <<<<<<<<<<<<<<<<<<<<<<<<
                    await asyncio.shield(main_loop())
                    # >>>>>>>>>>>>>>>>>>>>> Main loop <<<<<<<<<<<<<<<<<<<<<<<<

            except asyncio.CancelledError:
                logger.info("[BLE]: Received Stop Signal. Gracefully stopping impedance streaming")
                self.run_impedance = False
            finally:
                if self.connection_established and not self.run_impedance:
                    await send_stop_command_impedance()
        logger.debug("[BLE]: Impedance measurement successfully stopped")
