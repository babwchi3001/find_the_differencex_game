"""
Guardian API websocket utilities.
"""

import asyncio
import base64
import json
import socket
import time
import traceback
import websockets
from collections import namedtuple, deque
from typing import Optional

from .debug_logs import *

from .event_handlers import (
    LiveInsightsEvent,
    RealtimePredictionEvent,
    RecordingUpdateEvent,
    ClientError,
    default_console_handler,
)
from .utils import now, compute_rolling_average
from .websocket_messages import (
    StartNewRecording,
    SubscribeLiveStreamInsights,
    SubscribeRealtimePredictions,
    EndOngoingRecording,
)
from .ws_msg_handler import WsMsgHandler

Subscription = namedtuple("Subscription", ["identifiers", "event_type"])

logger = logging.getLogger("idun_guardian_sdk")


class GuardianRecording:
    """Main Guardian API client."""

    def __init__(self, ws_url: str, api_token: str) -> None:
        """Initialize Guardian API client.

        Args:
            debug (bool, optional): Enable debug logging. Defaults to True.
        """
        self.ping_timeout: int = 2
        self.retry_time: int = 2
        self.initial_receipt_timeout = 15
        self.receipt_timeout = self.initial_receipt_timeout
        self.sending_time_limit = 0.01
        self.bi_directional_timeout = 15
        self.last_saved_time = time.time()
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None  # type: ignore
        self.device_id = ""
        self.ws_url = ws_url
        self.ws_url_auth = f"{self.ws_url}?authorization={api_token}"
        self.ws_subscriptions = []
        self.msg_handler = WsMsgHandler()
        self.lag_values_size = 1000
        self.set_init_recording()
        self._subscribe_internal_msg_handlers()

    def set_init_recording(self):
        """
        Set/Reset initial recording properties.
        """
        self.connected = False
        self.data_to_send = False
        self.rec_started = False
        self.rec_data_incoming = False
        self.rec_ended = False
        self.recording_id = ""
        self.data_queue: asyncio.Queue = asyncio.Queue(maxsize=86400)
        self.ws_subscriptions_done = False
        self.latency_map = {}
        self.lag_values = deque(maxlen=self.lag_values_size)

    def _subscribe_internal_msg_handlers(self):
        self.msg_handler.subscribe(ClientError, default_console_handler)
        self.msg_handler.subscribe(RecordingUpdateEvent, self._handle_recording_update)

    def _handle_recording_update(self, event: RecordingUpdateEvent):
        status = event.message.get("status", None)
        if status == "NOT_STARTED":
            logger.debug(f"[API]: Setting recording_id: {event.message.get('recordingId')}")
            self.rec_started = True
            self.recording_id = event.message.get("recordingId")
        elif status == "ONGOING":
            self.rec_data_incoming = True
        elif status == "PROCESSING":
            self.rec_data_incoming = False
            pass
        elif status in ["COMPLETED", "FAILED"]:
            self.rec_ended = True
            logger.debug("[API]: Received final receipt! Finishing recording tasks.")
        else:
            logger.warning(f"[API]: Unexpected recording update status: {status}.")

    def _handle_latency_calculation(self, event: dict) -> None:
        """
        Calculates and prints the latency between sent and received packages.

        Args:
            event (dict): Event message from the websocket with "sequence" key
        """
        received_seq = event.get("sequence")
        sent_ts = self.latency_map.pop(received_seq, None)
        if sent_ts is None:
            return

        lag = int((time.time() - sent_ts) * 1000)
        self.lag_values.append(lag)
        rolling_average = compute_rolling_average(self.lag_values)
        logger.info(f"[API]: Packet number: {received_seq}. Lag: {lag}. Rolling Avg Lag: {rolling_average}")

    async def start_streaming(
        self,
        calc_latency: bool = False,
    ) -> None:
        """Connect to the Guardian API websocket.

        Args:
            calc_latency (bool): Enables calculation and display of data transmission latency to the cloud. Defaults to False.

        Raises:
            Exception: If the websocket connection fails
        """

        async def send_start_recording():
            msg = StartNewRecording(deviceId=self.device_id, deviceTs=now()).to_dict()
            if not self.data_queue.full():
                await asyncio.shield(self.data_queue.put(msg))
            else:
                await asyncio.shield(self.data_queue.get())
                await asyncio.shield(self.data_queue.put(msg))

        async def wait_recording_end():
            while True:
                if self.rec_ended:
                    break
                logger.debug("[API]: Waiting recording end message from the server...")
                await asyncio.sleep(1)

        async def load_data_to_send():
            data_valid = False
            self.data_to_send = None
            package = await self.data_queue.get()
            # TODO: Add more data validation or just always trust the data queue
            self.data_to_send = package
            data_valid = bool(self.data_to_send)

            return data_valid

        async def handle_api_subscriptions():
            while not self.ws_subscriptions_done:
                await asyncio.sleep(0.5)
                if self.connected and self.rec_started and self.rec_data_incoming:
                    logger.debug("[API]: Started checking API subscriptions!")
                    for subscription in self.ws_subscriptions:
                        logger.debug(f"[API]: Handling subscription: {subscription}")
                        msg = {}
                        if subscription.event_type == LiveInsightsEvent:
                            msg = SubscribeLiveStreamInsights(
                                deviceId=self.device_id,
                                recordingId=self.recording_id,
                                streamsTypes=subscription.identifiers,
                                deviceTs=now(),
                            ).to_dict()

                        if subscription.event_type == RealtimePredictionEvent:
                            logger.debug("[API]: Realtime Predictions subscription delay")
                            await asyncio.sleep(2)
                            msg = SubscribeRealtimePredictions(
                                deviceId=self.device_id,
                                recordingId=self.recording_id,
                                predictions=subscription.identifiers,
                                deviceTs=now(),
                            ).to_dict()

                        if not msg:
                            # Shouldn't happen
                            raise ValueError("Invalid subscription event type")

                        if not self.data_queue.full():
                            await asyncio.shield(self.data_queue.put(msg))
                        else:
                            await asyncio.shield(self.data_queue.get())
                            await asyncio.shield(self.data_queue.put(msg))

                    self.ws_subscriptions_done = True
                    logger.debug("[API]: Subscriptions messages sent to Data Queue!")
            logger.debug("[API]: Handle subscriptions task finished")

        async def send_messages():
            while True:
                if not self.connected or self.rec_ended:
                    break
                if await load_data_to_send():
                    await asyncio.shield(asyncio.sleep(self.sending_time_limit))  # Wait as to not overload the cloud
                    try:
                        await self.websocket.send(json.dumps(self.data_to_send))
                    except websockets.ConnectionClosed:
                        logger.warning(f"[API] Connection Closed. Message {self.data_to_send} was not sent")

                if self.data_to_send.get("action") == "endOngoingRecording":
                    logger.debug("[API]: Sending stop signal to the server...")
                    self.receipt_timeout = 1000  # Wait until necessary for the stop to be sent
                    try:
                        await asyncio.wait_for(wait_recording_end(), timeout=30)
                        logger.debug("[API]: The Recording has been correctly stopped")
                    except Exception as e:
                        logger.debug(
                            f"[API]: We could not stop the recording, we will retry to fix the problem. \n Error: {e}"
                        )
                    break

        async def receive_messages():
            self.last_saved_time = time.time()
            while True:
                if not self.connected or self.rec_ended:
                    break

                message = await asyncio.wait_for(self.websocket.recv(), timeout=self.receipt_timeout)
                self.last_saved_time = time.time()
                if not message:
                    continue

                event = {}
                try:
                    if isinstance(message, dict):
                        event = message
                    elif isinstance(message, (bytes, str)):
                        decoded = base64.b64decode(message).decode("utf-8")
                        event = json.loads(decoded)
                except Exception:
                    logger.debug(f"[API]: Error decoding message from the cloud: {message}")

                if not event:
                    continue

                action = event.get("action")
                if action is None:
                    logger.warning("[API]: Event without action will be discarded:", event)
                    continue
                if action == "liveStreamInsights":
                    self.msg_handler.publish(LiveInsightsEvent(event))
                    if calc_latency:
                        self._handle_latency_calculation(event)
                elif action == "realtimePredictionsResponse":
                    self.msg_handler.publish(RealtimePredictionEvent(event))
                elif action == "recordingUpdate":
                    self.msg_handler.publish(RecordingUpdateEvent(event))
                elif action == "clientError":
                    self.msg_handler.publish(ClientError(event))
                    raise Exception("Websocket Client Error:", event.get("message"))
                else:
                    logger.warning(f"[API]: Unhandled action: {action}. Message: {event}")

                if self.rec_ended:
                    break
                bi_directional_timeout()

        def bi_directional_timeout():
            time_without_data = time.time() - self.last_saved_time
            if time_without_data > self.bi_directional_timeout:
                raise asyncio.TimeoutError("Bidirection timeout error")

        def on_connection_initialise_variables():
            self.connected = True
            self.receipt_timeout = self.initial_receipt_timeout

        async def handle_cancelled_error():
            logger.debug("[API]: Handling cancel: ending recording")
            self.rec_ended = True
            if not self.rec_started:
                logger.debug("[API]: Recording has not started yet.")
                return

            logger.debug("[API]: Sending end recording signal to the Cloud")
            data_to_send = EndOngoingRecording(self.device_id, self.recording_id, now()).to_dict()
            if self.websocket and self.websocket.open:
                logger.debug("[API]: Websocket is already open, reusing it")
                await asyncio.shield(self.websocket.send(json.dumps(data_to_send)))
                return

            # If no websockket or connection
            async with websockets.connect(self.ws_url_auth) as end_websocket:
                logger.debug("[API]: Websocket is closed, creating a last connection to send the stop signal")
                await asyncio.shield(end_websocket.send(json.dumps(data_to_send)))

        while True:
            logging_connecting_to_cloud()
            try:
                async with websockets.connect(self.ws_url_auth) as self.websocket:  # type: ignore
                    if not self.rec_started:
                        log_sending_start_rec_info()
                        await send_start_recording()
                    try:
                        try:
                            on_connection_initialise_variables()
                            logging_connection(self.ws_url)
                            send_task = asyncio.create_task(send_messages())
                            receive_task = asyncio.create_task(receive_messages())
                            handle_subs_task = asyncio.create_task(handle_api_subscriptions())
                            task_list = [send_task, receive_task]
                            if not self.ws_subscriptions_done:
                                task_list.append(handle_subs_task)
                            await asyncio.gather(*task_list)
                        except (websockets.exceptions.ConnectionClosed,) as error:  # type: ignore
                            logger.debug("[API]: Websocket client connection closed")
                            self.connected = False
                            await asyncio.shield(asyncio.sleep(self.ping_timeout))
                            logging_reconnection()
                            continue
                        except asyncio.TimeoutError as error:
                            logger.debug("[API]: Timeout Error.")
                            self.connected = False
                            await asyncio.shield(asyncio.sleep(self.ping_timeout))
                            logging_reconnection()
                            continue
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
                            logger.debug("These tasks does not exist yet")

            except socket.gaierror as error:
                logging_gaieerror(error, self.retry_time)
                await asyncio.sleep(self.retry_time)
                continue

            except ConnectionRefusedError as error:
                logging_connection_refused(error, self.retry_time)
                await asyncio.sleep(self.retry_time)
                continue

            except Exception as error:
                logger.debug("[API]: Unhandled Error. Printing Traceback:")
                print("-------------------")
                traceback.print_exc()

            finally:
                # Otherwise new tasks will be created which is a problem
                try:
                    if not send_task.done():
                        send_task.cancel()
                    if not receive_task.done():
                        receive_task.cancel()
                except Exception as error:
                    logger.debug("These tasks does not exist yet")

            if self.rec_ended:
                logger.debug("[API]: Stop streaming data to the cloud")
                break

        logging_api_completed()
