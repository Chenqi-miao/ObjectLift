"""File protocol shared by the application and isolated generation worker."""
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Detection:
    id: str
    class_id: int
    label: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


@dataclass(frozen=True)
class GenerationRequest:
    job_id: str
    foreground_path: str
    output_dir: str
    preset: str


@dataclass
class GenerationResult:
    job_id: str
    status: Literal['succeeded', 'failed']
    model_path: str | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error_code: str | None = None
