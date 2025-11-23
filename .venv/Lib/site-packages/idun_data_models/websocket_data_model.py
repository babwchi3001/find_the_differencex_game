from datetime import datetime
from pydantic import BaseModel, constr
from .parameters import recordingID_regex, deviceID_regex


class Message(BaseModel, frozen=True):
    """
    A Message encapsulates encrypted device packets with metadata.
    The IDUN SDK sends Messages with device data to the IDUN Cloud through the websocket API.
    """

    recordingID: constr(regex=recordingID_regex)
    deviceID: constr(regex=deviceID_regex)
    deviceTimestamp: datetime
    connectionID: constr(max_length=256) | None = None
    payload: constr(max_length=40_000) | None = None
    impedance: float | None = None

    # DEPRECATED: these fields will be replaced by explicit API calls
    stop: bool | None = None
    "Signal that the frontend sends to stop the recording"
    recorded: bool | None = None
    "Signal that the recorder sends to signal that batch processing is complete"
    enableStreamer: bool | None = None
    "Signal that the frontend can send to disable live streaming"
