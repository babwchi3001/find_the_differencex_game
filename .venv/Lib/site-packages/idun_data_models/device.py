from pydantic.dataclasses import dataclass
from functools import reduce

@dataclass(frozen=True)
class DevicePacket:
    "A single packet of data produced by the device"
    # [samples] Array of samples (eg. 20)
    ch1: list[int]
    # [samples]
    ch2: list[int]
    # [imuSamples][xyz] Array of 3D samples
    acc: list[list[int]]
    magn: list[list[int]]
    gyro: list[list[int]]

    def __hash__(self) -> int:
        def plushash(a: int, b: int) -> int:
            return hash(a) + hash(b)

        def hashreduce(x) -> int:
            return reduce(plushash, x)

        def hashmap(x) -> int:
            return hashreduce(map(hashreduce, x))

        return hashmap([self.ch1, self.ch2] + self.acc + self.magn + self.gyro)

def emptyPacket() -> DevicePacket:
    return DevicePacket([], [], [[]], [[]], [[]])