import json, asyncio, time
from datetime import datetime, timedelta
from pydantic import parse_obj_as, ValidationError
from idun_data_models import (
    Metadata_in,
    Metadata_out,
    Marker,
    MAX_MARKER_COUNT,
)
from .config import settings
from .igeb_utils import request


class MetadataClient:
    def __init__(
        self, deviceID, recordingID, password, httpClient=settings.REST_API_LOGIN
    ):
        self.deviceID = deviceID
        self.recordingID = recordingID
        self.client = httpClient
        self.password = password

    async def create_metadata(self, metadata):
        response = await request(
            "post",
            self.client,
            self.deviceID,
            recordingApiPath=f"/{self.recordingID}/metadata",
            payload=metadata,
            password=self.password,
        )
        return parse_obj_as(Metadata_out, json.loads(response))

    async def list_metadata(self, params):
        response = await request(
            "get",
            self.client,
            self.deviceID,
            recordingApiPath=f"/{self.recordingID}/metadata",
            params=params,
            password=self.password,
        )
        return parse_obj_as(list[Metadata_out], json.loads(response))

    async def get_metadata(self, metadataID):
        response = await request(
            "get",
            self.client,
            self.deviceID,
            recordingApiPath=f"/{self.recordingID}/metadata/{metadataID}",
            password=self.password,
        )
        return parse_obj_as(Metadata_out, json.loads(response))

    async def create_markers(self, metadataID, markers):
        response = await request(
            "post",
            self.client,
            self.deviceID,
            recordingApiPath=f"/{self.recordingID}/metadata/{metadataID}/markers",
            payload=markers,
            password=self.password,
        )
        return json.loads(response)

    async def get_markers(self, metadataID, params):
        response = await request(
            "get",
            self.client,
            self.deviceID,
            recordingApiPath=f"/{self.recordingID}/metadata/{metadataID}/markers",
            params=params,
            password=self.password,
        )
        return parse_obj_as(list[Marker], json.loads(response))
