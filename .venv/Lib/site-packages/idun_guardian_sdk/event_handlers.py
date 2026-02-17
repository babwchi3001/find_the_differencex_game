from .event import Event

import logging


class LiveInsightsEvent(Event):
    def __init__(self, message: dict):
        self.message = message


class RealtimePredictionEvent(Event):
    def __init__(self, message: dict):
        self.message = message


class ClientError(Event):
    def __init__(self, message: dict):
        self.message = message


class RecordingUpdateEvent(Event):
    def __init__(self, message: dict):
        self.message = message


def default_console_handler(event: Event):
    print(f"Received new event {type(event)}. Message: {event.message}")
