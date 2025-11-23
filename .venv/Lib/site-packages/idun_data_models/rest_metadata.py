from enum import Enum
from datetime import datetime
from pydantic import BaseModel, constr, conlist, validator
from .parameters import MAX_ID_LENGTH, MAX_MARKER_COUNT
from .validation import check_dict_size


class experiment_names(str, Enum):
    Sleep = "sleep"
    EoEc = "eoec"
    Nap = "nap"


class comfort_values(str, Enum):
    Poor = "poor"
    Good = "good"
    Excellent = "excellent"


class Marker(BaseModel):
    "Time-based metadata"
    timestamp: datetime
    marker: dict

    @validator("marker")
    def validate_marker_size(cls, value, field):
        check_dict_size(value, field)
        return value


class MarkerOut(Marker):
    id: int | None = None
    "[deprecated] This field will be removed in a future release in favor of the `timestamp` as a natural key"


class Metadata_in(BaseModel):
    "Metadata input format"

    displayName: constr(max_length=MAX_ID_LENGTH) | None = None
    "User-friendly name used in the UI"
    metadata: dict | None = None
    "Metadata must follow the validation schema"
    markers: conlist(Marker, max_items=MAX_MARKER_COUNT) | None = None
    "Markers must always have a `timestamp` field"

    metadataValidationSchemaID: int | None = None
    "If a validation schema is linked, it must already exist"
    markerValidationSchemaID: int | None = None
    "If a validation schema is linked, it must already exist"

    attachedMetadataValidationSchema: dict | None = None
    "Directly attached validation schema will be implicitly created"
    attachedMarkerValidationSchema: dict | None = None
    "Directly attached validation schema will be implicitly created"

    experiment_name: experiment_names | None = None
    "Equivalent to passing this value through the `metadata`"
    comfort: comfort_values | None = None
    "Equivalent to passing this value through the `metadata`"

    @validator(
        "metadata", "attachedMetadataValidationSchema", "attachedMarkerValidationSchema"
    )
    def validate_metadata(cls, value, field):
        if value is None:
            return
        check_dict_size(value, field)
        if exp_name := value.get("experiment_name"):
            if not exp_name in [name.value for name in experiment_names]:
                raise ValueError(
                    f"Only accepted experiment names: {[v.value for v in experiment_names]}"
                )

        if comfort := value.get("comfort"):
            if not comfort in [name.value for name in comfort_values]:
                raise ValueError(
                    f"Only accepted comfort values: {[v.value for v in comfort_values]}"
                )
        # TODO: if a schema is attached, validate the metadata and markers
        return value


class Metadata_out(Metadata_in):
    "Metadata output format"

    id: int | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None
    markers_count: int | None = None
