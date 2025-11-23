import random


def mock_cloud_package():
    """Mock a package from the cloud"""
    return {
        "timeStamp": "deviceID",
        "bp_filter_eeg": random.randint(-500, 500) / 10,
    }
