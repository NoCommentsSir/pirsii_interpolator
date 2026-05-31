from pydantic import BaseModel, ConfigDict

class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    video_id: int
    staged_video_uri: str
    validation_status: str
    queue_status: str
    output_video_uri: str
