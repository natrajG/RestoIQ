from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]


class CameraRegionInput(BaseModel):
    table_id: int
    name: ShortText
    polygon: list[tuple[float, float]] = Field(min_length=3, max_length=32)


class CameraInput(BaseModel):
    restaurant_id: int
    name: ShortText
    source_type: Literal["rtsp", "recording"] = "rtsp"
    stream_url: str | None = Field(default=None, max_length=2048)
    floor_id: int | None = None
    regions: list[CameraRegionInput] = Field(default_factory=list)


class CameraUpdateInput(BaseModel):
    name: ShortText | None = None
    floor_id: int | None = None


class CameraRegionsUpdateInput(BaseModel):
    regions: list[CameraRegionInput] = Field(max_length=100)


class CameraObservationInput(BaseModel):
    camera_id: int
    restaurant_id: int
    table_id: int | None = None
    observation_type: str = Field(min_length=1, max_length=48)
    confidence: Decimal | None = Field(default=None, ge=0, le=1, decimal_places=4)
    evidence: dict = Field(default_factory=dict)


class StaffTaskAssignmentInput(BaseModel):
    employee_id: int


class StaffTaskCompletionInput(BaseModel):
    note: str | None = Field(default=None, max_length=300)
