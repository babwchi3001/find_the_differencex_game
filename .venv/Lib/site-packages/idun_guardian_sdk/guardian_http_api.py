import json
import logging
import os
import requests
from typing import List, Optional
from urllib.parse import urlparse, unquote

from .constants import PLATFORM
from .exceptions import APIRequestError
from .types import FileTypes


logger = logging.getLogger("idun_guardian_sdk")


class ReportResponse:
    def __init__(self, status, url):
        self.status = status
        self.url = url


class CustomSession(requests.Session):
    def __init__(self, base_url=None, api_token=None, *args, **kwargs):
        super(CustomSession, self).__init__(*args, **kwargs)
        self.base_url = base_url
        # You can also add your custom headers here if needed
        self.headers.update({"Authorization": api_token, "X-Platform": PLATFORM, "Connection": "close"})

    def request(self, method, url, *args, **kwargs):
        # Prepend base URL if it exists and the url is a relative path
        if self.base_url and not url.startswith(("http://", "https://")):
            url = self.base_url.rstrip("/") + "/" + url.lstrip("/")
        response = super(CustomSession, self).request(method, url, *args, **kwargs)
        logger.debug(f"[API] Received response with status code {response.status_code}")
        return response


class GuardianHttpAPI:
    """
    Class that encapsulates the HTTP API calls to the Idun Guardian API.
    """

    def __init__(self, url: str, api_token: str):
        """
        Args:
            url (str): the base URL of the API
            api_token (str): the API token to authenticate the requests
        """
        self._base_url = url
        self._api = CustomSession(base_url=self._base_url, api_token=api_token)

    def end_recording(self, recording_id: str):
        """
        Send end signal to a recording.

        Args:
            recording_id (str): The id of the recording.
        """
        r = self._api.post(f"/api/recording/{recording_id}/end-recording")
        if r.status_code == 200:
            logger.info(f"[API]: Recording {recording_id} ended successfully")
        else:
            raise APIRequestError(f"Failed to end recording {recording_id}. {r.text}")

    def update_recording_tags(self, recording_id: str, tags: List[str]):
        """
        Updates the tags of a recording.

        Args:
            recording_id (str): The id of the recording.
            tags (list): The tags to update.
        """
        self._api.post(f"/api/recording/{recording_id}/tags", json={"tags": tags})

    def update_recording_display_name(self, recording_id: str, display_name: str):
        """
        Updates the display name of a recording.

        Args:
            recording_id (str): The id of the recording.
            display_name (str): The new display name.
        """
        self._api.post(f"/api/recording/{recording_id}/update", json={"displayName": display_name})

    def download_recording(self, recording_id: str, file_type: FileTypes):
        """
        Downloads the recording data file.

        Args:
            recording_id (str): the id of the recording. Must be a COMPLETED recording.
            file_type (idun_guardian_sdk.FileTypes): possible values: EGG, IMU, IMPEDANCE

        Returns:
            str: The presigned signed URL to download the file
        """
        resp = self._api.get(f"/api/recording/{recording_id}/data/{file_type.name}/download")
        if not resp.ok:
            raise APIRequestError(f"Failed to download recording {recording_id}. {resp.text}")
        res = json.loads(resp.text)
        url = res.get("url")
        return url

    def generate_daytime_report(self, recording_id: str):
        """
        Send signal to the API to generate the daytime report for a recording.

        Args:
            recording_id (str): The id of the recording. Must be a COMPLETED recording.

        Raises:
            APIRequestError: If the request or the report generation fails
        """
        resp = self._api.post(f"/api/recording/{recording_id}/daytime-report/generate")
        if resp.status_code == 200:
            logger.info(f"[API]: Successfully requested daytime report for recording {recording_id}")
            data = resp.json()
            if "reportId" in data:
                return data["reportId"]
            else:
                raise
        else:
            raise APIRequestError(
                f"Failed to request daytime report for recording {recording_id}. Status code: {resp.status_code}, Response: {resp.text}"
            )

    def generate_sleep_report(self, recording_id: str):
        """
        Sends signal to the API to generate the sleep report for a recording.

        Args:
            recording_id (str): The id of the recording. Must be a COMPLETED recording.

        Raises:
            APIRequestError: If the request or the report generation fails
        """
        resp = self._api.post(f"/api/recording/{recording_id}/sleep-report/generate")
        if resp.status_code == 200:
            logger.info(f"[API]: Successfully requested sleep report for recording {recording_id}")
            logger.info(f"[API]: Sleep Report Started: {resp.json()}")
            data = resp.json()
            if "reportId" in data:
                return data["reportId"]
            else:
                raise
        else:
            raise APIRequestError(
                f"Failed to request sleep report for recording {recording_id}. Status code: {resp.status_code}, Response: {resp.text}"
            )

    def get_recording_reports(self, recording_id: str):
        """
        Get the reports for a recording.

        Args:
            recording_id (str): The id of the recording.

        Returns:
            dict: the reports for the recording
        """
        resp = self._api.get(f"/api/recording/{recording_id}/reports")
        if resp.ok:
            return resp.json()
        else:
            raise APIRequestError(
                f"Failed to get reports for recording {recording_id}. Status code: {resp.status_code}, Response: {resp.text}"
            )

    def download_daytime_report(self, recording_id: str) -> ReportResponse:
        """
        Downloads the daytime report for a recording.

        Args:
            recording_id (str): The id of the recording. The report must be generated first.

        Returns:
            ReportResponse: object containing the status and the presigned signed URL to download the file

        Raises:
            APIRequestError: If the request or the report download fails
        """
        resp = self._api.get(f"/api/recording/{recording_id}/daytime-report/download")
        res = json.loads(resp.text)
        url = res.get("url")
        if resp.status_code != 200:
            raise APIRequestError(
                f"Failed to download daytime report for recording {recording_id}. {res.get('message')}"
            )
        return ReportResponse(res.get("status"), url)

    def download_sleep_report(self, recording_id: str) -> ReportResponse:
        """
        Downloads the sleep report for a recording.

        Args:
            recording_id (str): The id of the recording. The report must be generated first.

        Returns:
            ReportResponse: object containing the status and the presigned signed URL to download the file

        Raises:
            APIRequestError: If the request or the report download fails
        """
        logger.warning("This method will be deprecated in the future. Use download_sleep_report_by_id instead.")
        resp = self._api.get(f"/api/recording/{recording_id}/sleep-report/download")
        res = json.loads(resp.text)

        if resp.status_code != 200:
            raise APIRequestError(f"Failed to download sleep report for recording {recording_id}. {res.get('message')}")

        return ReportResponse(res.get("status"), res.get("url"))

    def download_daytime_report_by_id(self, report_id: str) -> ReportResponse:
        """
        Downloads the daytime report for a recording.

        Args:
            recording_id (str): The id of the recording. The report must be generated first.

        Returns:
            ReportResponse: object containing the status and the presigned signed URL to download the file

        Raises:
            APIRequestError: If the request or the report download fails
        """
        resp = self._api.get(f"/api/report/{report_id}/daytime-report/download")
        res = json.loads(resp.text)

        if resp.status_code != 200:
            raise APIRequestError(f"Failed to download daytime report with id {report_id}. {res.get('message')}")

        return ReportResponse(res.get("status"), res.get("reportUrl"))

    def download_sleep_report_by_id(self, report_id: str) -> ReportResponse:
        """
        Downloads the sleep report by a given report id.
        """
        resp = self._api.get(f"/api/report/{report_id}/sleep-report/download")
        res = json.loads(resp.text)

        if resp.status_code != 200:
            raise APIRequestError(f"Failed to download sleep report with id {report_id}. {res.get('message')}")

        return ReportResponse(res.get("status"), res.get("reportUrl"))

    def download_sleep_report_raw_data(self, recording_id: str) -> ReportResponse:
        """
        Downloads the sleep report raw data for a recording.

        Args:
            recording_id (str): The id of the recording. The report must be generated first.
        """
        resp = self._api.get(f"/api/recording/{recording_id}/sleep-report-results/download")
        res = json.loads(resp.text)

        if resp.status_code != 200:
            raise APIRequestError(
                f"Failed to download sleep report raw data for recording {recording_id}. {res.get('message')}"
            )
        return ReportResponse(res.get("status"), res.get("url"))

    def download_daytime_report_raw_data(self, recording_id: str) -> ReportResponse:
        """
        Downloads the daytime report raw data for a recording.

        Args:
            recording_id (str): The id of the recording. The report must be generated first.
        """
        resp = self._api.get(f"/api/recording/{recording_id}/daytime-report-results/download")
        res = json.loads(resp.text)

        if resp.status_code != 200:
            raise APIRequestError(
                f"Failed to download daytime report raw data for recording {recording_id}. {res.get('message')}"
            )
        return ReportResponse(res.get("status"), res.get("url"))

    def save_file_from_s3(self, url: str, file_path: str):
        """
        Saves a file from an S3 presigned URL to the local file system.

        Args:
            url (str): the presigned URL to download the file
            file_path (str): the path where to save the file. If None, the file is saved in the current directory

        Returns:
            str: the full path of the saved file

        Raises:
            ValueError: If the URL is not valid
        """
        parsed_url = urlparse(url)
        file_name = os.path.basename(parsed_url.path)
        # Unquote in case the file name is URL encoded
        file_name = unquote(file_name)
        full_path = file_name

        if file_path is not None:
            full_path = os.path.join(file_path, file_name)
            os.makedirs(file_path, exist_ok=True)

        r = requests.get(url, allow_redirects=True)

        if r.status_code == 200:
            # Open the file in binary write mode and save the content
            with open(full_path, "wb") as file:
                file.write(r.content)
            logger.info(f"[API]: File saved: '{full_path}'")
        else:
            raise ValueError(f"The provided url is not valid. {url}")
        return full_path

    def get_recordings(self, limit: int = 200, status: Optional[str] = None, page_index: Optional[int] = None):
        """
        Returns all the recordings. You can filter by status and limit the number of results.

        Args:
            limit (int): how many recordings to download. Default is 200
            status (str, optional): the status of the recording. Possible values: NOT_STARTED, ONGOING, PROCESSING, COMPLETED, FAILED
            page_index (int, optional): used in case of paginating the results. Pass the lastEvaluatedKey from the previous response

        Returns:
            dict: the result of the query. All the recordings and the lastEvaluatedKey for pagination.
                If lastEvaluatedKey is None, there are no more results
        """
        query_params = {"pageSize": limit, "status": status, "lastEvaluatedKey": page_index}
        filtered_query_params = {k: v for k, v in query_params.items() if v is not None}
        resp = self._api.get("/api/recording", params=filtered_query_params)
        return json.loads(resp.text)

    def delete_recording(self, recording_id: str):
        """
        Completely deletes a recording.

        Args:
            recording_id (str): The id of the recording to be deleted
        """
        resp = self._api.delete(f"api/recording/{recording_id}")
        if resp.ok:
            logger.info(f"[API]: Recording {recording_id} deleted successfully")
        else:
            logger.warning(f"[API]: Failed to delete recording {recording_id}. {resp.text}")

    def get_user_info(self):
        """
        Get the user information.

        Returns:
            dict: the user information with the following keys:
                - idun_id
                - device_id
                - hardware_version
                - commercial_version
        """
        result = self._api.get("/api/user-info")
        if result.status_code != 200:
            raise APIRequestError(result.text)

        r = json.loads(result.text)
        logger.debug(f"[API]: User INFO: {r}")
        return {
            "idun_id": r["idun_id"],
            "device_id": r["device_id"],
            "hardware_version": r["hardware_version"],
            "commercial_version": r["commercial_version"],
        }

    def upload_hardware_version(self, hardware_version: str):
        """
        Upload the device hardware version to the API.

        Args:
            hardware_version (str): The hardware version string

        Returns:
            bool: True if the hardware version was uploaded successfully, False otherwise
        """
        data = {"hardware_version": hardware_version}
        result = self._api.post("/api/set-device-type", json=data)
        if result.status_code != 200:
            return False

        logger.info(f"[API]: Device hardware version uploaded successfully: {hardware_version}")
        return True

    def generate_brain_art(self, recording_id, calm_score):
        res = self._api.post("/api/brain-image/generate", data={"recordingId": recording_id, "calmScore": calm_score})
        return res
