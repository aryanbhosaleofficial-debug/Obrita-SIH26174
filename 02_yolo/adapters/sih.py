"""The only active bridge to SIH shared contracts. No Module 01 changes."""

from dataclasses import fields
from types import SimpleNamespace

from yolo.core.contracts import DetectorConfig as InternalConfig
from yolo.core.contracts import InputFrame, SourceFrame

from shared.config import DetectorConfig
from shared.diagnostics import Diagnostic, NoticeCode, WarningCode
from shared.enums.module_status import ModuleStatus
from shared.errors import InitializationError
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import BoundingBox, Detection
from shared.schemas.prepared_frame import PreparedFrame

SIH_TYPES = SimpleNamespace(
    Diagnostic=Diagnostic,
    WarningCode=WarningCode,
    NoticeCode=NoticeCode,
    ModuleStatus=ModuleStatus,
    InitializationError=InitializationError,
    ResultFrame=ObjectFrame,
    Detection=Detection,
    BoundingBox=BoundingBox,
)


def adapt_config(config):
    if not isinstance(config, DetectorConfig):
        raise TypeError("Module 02 requires shared.config.DetectorConfig")
    return InternalConfig(
        **{f.name: getattr(config, f.name) for f in fields(InternalConfig)}
    )


def adapt_prepared(prepared):
    if not isinstance(prepared, PreparedFrame):
        raise TypeError("YoloPipeline consumes shared.schemas.PreparedFrame")
    source = prepared.source
    if source is None:
        raise ValueError("PreparedFrame must retain its source")
    return InputFrame(
        prepared.image,
        prepared.scale_x,
        prepared.scale_y,
        SourceFrame(
            source.frame_id,
            source.timestamp_s,
            source.image,
            source.width,
            source.height,
            source.source_id,
            source.session_id,
            source.color_format,
        ),
        status=prepared.status,
        warnings=list(prepared.warnings),
        notices=list(prepared.notices),
        accepted=prepared.accepted,
        reset_required=prepared.reset_required,
    )
