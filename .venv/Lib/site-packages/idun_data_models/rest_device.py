from enum import Enum
from datetime import datetime
from pydantic import BaseModel, AnyHttpUrl


class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class PresignedUrl(BaseModel):
    method: HttpMethod
    url: AnyHttpUrl
    fields: dict | None = None
    """
    Form fields that need to be included with a POST request. Without these form fields, S3 will reject the request.
    For example:

        <form action="<YOUR_PRESIGNED_URL>" method="post" enctype="multipart/form-data">
            <input type="hidden" name="key" value="<FIELD_VALUE>">
            <input type="hidden" name="AWSAccessKeyId" value="<FIELD_VALUE>">
            <input type="hidden" name="policy" value="<FIELD_VALUE>">
            <input type="hidden" name="signature" value="<FIELD_VALUE>">
            <!-- more fields here -->
            <input type="file" name="file">
            <input type="submit" name="submit" value="Upload to Amazon S3">
        </form>
    """
    expiration: datetime
    "Past this timestamp the URL is invalid"
