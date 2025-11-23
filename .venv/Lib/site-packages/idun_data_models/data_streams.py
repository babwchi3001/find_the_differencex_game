from collections import deque
from pydantic import BaseModel, constr
from .parameters import deviceID_regex


class EEGInference(BaseModel):
    "EEG data (potentially processed) as inference result"
    ch1: deque[float]
    timestamp: deque[float]

    def clear(self):
        self.ch1.clear()
        self.timestamp.clear()

    def __len__(self):
        return len(self.ch1)

    @classmethod
    def with_max_capacity(cls, max_capacity):
        return cls(
            ch1=deque(maxlen=int(max_capacity)),
            timestamp=deque(maxlen=int(max_capacity)),
        )


class DataStreams(BaseModel):
    "Real time data streams available to return to the client"
    # NOTE: add only bool flags for various data streams

    bp_filter_eeg: bool = False
    "Enables a stream of bandpass filtered EEG signal"
    raw_eeg: bool = False
    "Enables a stream of raw EEG signal"
    # The following options are not yet supported
    # spectrogram: bool= False

    def streaming_enabled(self):
        # NOTE: extend this expression if you add more data streams
        return self.bp_filter_eeg or self.raw_eeg


class DataStreamContent(BaseModel):
    "Content of the realtime data streams defined in `DataStreams`"

    deviceID: constr(regex=deviceID_regex) | None = None
    bp_filter_eeg: EEGInference | None = None
    raw_eeg: EEGInference | None = None
    # NOTE: match any new type in DataStreams here by name

    def clear(self):
        if self.bp_filter_eeg:
            self.bp_filter_eeg.clear()
        if self.raw_eeg:
            self.raw_eeg.clear()

    def __len__(self):
        return (len(self.bp_filter_eeg) if self.bp_filter_eeg else 0) + (
            len(self.raw_eeg) if self.raw_eeg else 0
        )

    @classmethod
    def from_datastream(cls, datastream: DataStreams, max_buffer_length):
        return cls(
            bp_filter_eeg=EEGInference.with_max_capacity(max_buffer_length)
            if datastream.bp_filter_eeg
            else None,
            raw_eeg=EEGInference.with_max_capacity(max_buffer_length)
            if datastream.raw_eeg
            else None,
        )
