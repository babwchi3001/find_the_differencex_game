from pydantic import BaseSettings


class Settings(BaseSettings):
    """
    Microservice settings. They can be set as environment variables.
    """

    # GDK 2.0 BLE characteristic
    STARTBYTE: str = "0xF0"
    ENDBYTE: str = "0x0F"
    DEVICE_ID: str = "703DF80E-F543-1947-C0AD-2178ACACAFC7"
    UUID_MEAS_EEGIMU: str = "beffd56c-c915-48f5-930d-4c1feee0fcc4"
    UUID_MEAS_EEG: str = "beffd56c-c915-48f5-930d-4c1feee0fcc5"
    UUID_MEAS_IMP: str = "beffd56c-c915-48f5-930d-4c1feee0fcc8"
    UUID_DEVICE_SERVICE: str = "0000180a-0000-1000-8000-00805f9b34fb"
    UUID_MAC_ID: str = "00002a25-0000-1000-8000-00805f9b34fb"
    UUID_FIRMWARE_VERSION: str = "00002a26-0000-1000-8000-00805f9b34fb"
    UUID_BATTERY_ID: str = "00002a19-0000-1000-8000-00805f9b34fb"
    UUID_CFG: str = "beffd56c-c915-48f5-930d-4c1feee0fcc9"
    UUID_CMD: str = "beffd56c-c915-48f5-930d-4c1feee0fcca"
    LED_ON_CFG: str = "d1"
    LED_OFF_CFG: str = "d0"
    NOTCH_FREQ_50_CFG: str = "n0"
    NOTCH_FREQ_60_CFG: str = "n1"
    START_CMD: str = "M"  #'\x62' #b -> start measurement
    STOP_CMD: str = "S"  # '\x73' #s -> stop measurement
    START_IMP_CMD: str = "Z"  # '\x7a' #z -> start impedance
    STOP_IMP_CMD: str = "X"  # '\x78' #x -> stop impedance
    UUID_BATT_GDK: str = "00002a19-0000-1000-8000-00805f9b34fb"
    CONNECTION_TIME = 60

    # Websocket Connection API Gateway
    WS_IDENTIFIER: str = "wss://wpcg36nil5.execute-api.eu-central-1.amazonaws.com/v1/"

    # REST API Gateway
    REST_API_LOGIN: str = "https://d3pq71txhb.execute-api.eu-central-1.amazonaws.com/"


settings = Settings()
