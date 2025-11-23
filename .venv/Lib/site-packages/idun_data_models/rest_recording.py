"""
This module defines data classes that are used by the IDUN Data API, defined with Pydantic.
"""

import re
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, constr
from .parameters import MAX_ID_LENGTH, recordingID_regex, deviceID_regex
from .data_streams import DataStreams


class RecordingConfig(BaseModel):
    data_stream_subscription: DataStreams | None = None
    "Subscribe to real time data streams. No data stream by default."


class recordingstatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    ONGOING = "ONGOING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class _RecordingStatus(BaseModel):
    stopped: bool
    "Is the recording still receiving data?"


class RecordingStatusIn(_RecordingStatus):
    pass


class RecordingStatusOut(_RecordingStatus):
    status: recordingstatus | None = None
    message: str | None = None
    "Explanation about the current status"
    startDeviceTimestamp: datetime | None = None
    """Device timestamp of the first message in the recording.
    It is provided by the client, so it can be unreliable for BI purposes.
    """
    stopDeviceTimestamp: datetime | None = None
    """Device timestamp of the last message in the recording.
    It is provided by the client, so it can be unreliable for BI purposes.
    """
    createdAt: datetime | None = None
    """Local timestamp of the API at the moment that this recording was created.
    """
    stoppedAt: datetime | None = None
    """Local timestamp of the API at the moment that this recording was stopped.
    """


def regex_validation(regex, v, field):
    if not re.match(regex, v):
        raise ValueError(f"{field} must follow the pattern: {regex}")


class _Recording(BaseModel):
    recordingID: constr(regex=recordingID_regex)
    deviceID: constr(regex=deviceID_regex) | None = None
    "[deprecated] this field no longer has any function"
    displayName: constr(max_length=MAX_ID_LENGTH)
    "User-friendly name used in the UI"


class RecordingIn(_Recording):
    """
    RecordingIn can be used to create/update recordings in the IDUN REST API.
    A Recording is a contiguous data capture session of the IDUN Guardian through a specific frontend client.
    """

    config: RecordingConfig | None = None


class RecordingOut(_Recording):
    """
    RecordingOut is returned by the IDUN REST API to describe existing recordings.
    A Recording is a contiguous data capture session of the IDUN Guardian through a specific frontend client.
    """

    status: RecordingStatusOut | None = None
    config: RecordingConfig | None = None
