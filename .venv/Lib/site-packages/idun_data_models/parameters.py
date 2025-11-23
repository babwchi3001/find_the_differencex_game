import re

MAX_ID_LENGTH = 64
ID_REGEX = r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0," + re.escape(str(MAX_ID_LENGTH - 1)) + r"}$"
deviceID_regex = ID_REGEX
"DeviceIDs must follow this pattern"
recordingID_regex = ID_REGEX
"RecordingIDs must follow this pattern"

MAX_MARKER_COUNT = 1000
"Max number of markers currently allowed to be attached to metadata"
MAX_METADATA_COUNT = 50
"Max number of metadata currently allowed to be attached to a recording"
MAX_METADATA_SIZE_BYTES = 100_000
"""Max size of a single metadata dict field in bytes.
It is system-dependent, therefore leave at least a factor-2 size as safety margin.
"""
