import time


class PollingService:
    def poll_until_ready(self, target_method, timeout_seconds=900, *args, **kwargs):
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            response = target_method(*args, **kwargs)
            if response.status == "READY" or response.status == "COMPLETED":
                return response.url
            time.sleep(1)

        raise Exception("Timeout exceeded!")
