from typing import Optional, List
from pydantic import BaseModel, field_validator


class GenerateModel(BaseModel):
    request: str
    analysis_id: Optional[str] = None
    lang: Optional[str] = None


class GeneratePreviewModel(BaseModel):
    request: str
    analysis_id: Optional[str] = None
    lang: Optional[str] = None
    use_producer_advice: bool = False
    only_compose_prompt: bool = False
    image_base64: Optional[str] = None
    image_mime_type: Optional[str] = None
    # None = auto-detect (True when use_producer_advice=False, False otherwise)
    direct_image_mode: Optional[bool] = None


class CreateCompetitorAnalysisModel(BaseModel):
    name: str
    description: Optional[str] = None
    channels: List[str] = []
    lang: str
    project_channel_url: Optional[str] = None
    
    @field_validator('channels')
    @classmethod
    def validate_channels_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one channel is required to create an analysis')
        return v


class OrderVideoReportModel(BaseModel):
    """Request body for ordering a video GPT report"""
    analysis_id: str


class AddProjectEmployeeRequest(BaseModel):
    employee_email: str