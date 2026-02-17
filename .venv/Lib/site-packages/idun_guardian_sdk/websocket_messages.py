from . import constants


class WebSocketMessage:
    def __init__(self, action, deviceId):
        self.version = 1
        self.platform = constants.PLATFORM
        self.action = action
        self.deviceId = deviceId


class SubscribeRealtimePredictions(WebSocketMessage):
    def __init__(self, deviceId, recordingId, predictions, deviceTs):
        super().__init__(
            action="subscribeRealtimePredictions",
            deviceId=deviceId,
        )
        self.predictions: list = predictions
        self.deviceTs = deviceTs
        self.recordingId = recordingId

    def to_dict(self):
        return {
            "version": self.version,
            "platform": self.platform,
            "action": self.action,
            "deviceId": self.deviceId,
            "deviceTs": self.deviceTs,
            "recordingId": self.recordingId,
            "predictions": list(self.predictions),
        }


class SubscribeLiveStreamInsights(WebSocketMessage):
    def __init__(self, deviceId, recordingId, streamsTypes, deviceTs):
        super().__init__(
            action="subscribeLiveStreamInsights",
            deviceId=deviceId,
        )
        self.streamsTypes = streamsTypes
        self.deviceTs = deviceTs
        self.recordingId = recordingId

    def to_dict(self):
        return {
            "version": self.version,
            "platform": self.platform,
            "action": self.action,
            "deviceId": self.deviceId,
            "deviceTs": self.deviceTs,
            "recordingId": self.recordingId,
            "streamsTypes": list(self.streamsTypes),
        }


class StartNewRecording(WebSocketMessage):
    def __init__(self, deviceId, deviceTs):
        super().__init__(
            action="startNewRecording",
            deviceId=deviceId,
        )
        self.deviceTs = deviceTs

    def to_dict(self):
        return {
            "version": self.version,
            "platform": self.platform,
            "action": self.action,
            "deviceId": self.deviceId,
            "deviceTs": self.deviceTs,
        }


class PublishRawMeasurements(WebSocketMessage):
    def __init__(self, deviceId, deviceTs, event, recordingId, sequence):
        super().__init__(
            action="publishRawMeasurements",
            deviceId=deviceId,
        )
        self.deviceTs = deviceTs
        self.event = event
        self.recordingId = recordingId
        self.sequence = sequence

    def to_dict(self):
        return {
            "version": self.version,
            "platform": self.platform,
            "action": self.action,
            "deviceId": self.deviceId,
            "deviceTs": self.deviceTs,
            "event": self.event,
            "recordingId": self.recordingId,
            "sequence": self.sequence,
        }


class UnsubscribeRealtimePredictions(WebSocketMessage):
    def __init__(self, deviceId, recordingId, deviceTs):
        super().__init__(
            action="unsubscribeRealtimePredictions",
            deviceId=deviceId,
        )
        self.deviceTs = deviceTs
        self.recordingId = recordingId

    def to_dict(self):
        return {
            "version": self.version,
            "platform": self.platform,
            "action": self.action,
            "deviceId": self.deviceId,
            "deviceTs": self.deviceTs,
            "recordingId": self.recordingId,
        }


class UnsubscribeLiveStreamInsights(WebSocketMessage):
    def __init__(self, deviceId, recordingId, deviceTs):
        super().__init__(
            action="subscribeLiveStreamInsights",
            deviceId=deviceId,
        )
        self.deviceTs = deviceTs
        self.recordingId = recordingId
        self.streamTypes = set()

    def to_dict(self):
        return {
            "version": self.version,
            "platform": self.platform,
            "action": self.action,
            "deviceId": self.deviceId,
            "deviceTs": self.deviceTs,
            "recordingId": self.recordingId,
            "streamTypes": list(self.streamTypes),
        }


class EndOngoingRecording(WebSocketMessage):
    def __init__(self, deviceId, recordingId, deviceTs):
        super().__init__(
            action="endOngoingRecording",
            deviceId=deviceId,
        )
        self.deviceTs = deviceTs
        self.recordingId = recordingId

    def to_dict(self):
        return {
            "version": self.version,
            "platform": self.platform,
            "action": self.action,
            "deviceId": self.deviceId,
            "deviceTs": self.deviceTs,
            "recordingId": self.recordingId,
        }
