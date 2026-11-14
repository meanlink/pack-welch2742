from pydantic import BaseModel, Field
class JobInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    dataset_id: int
    params: dict = Field(default_factory=dict)
class RecomputeInput(BaseModel):
    reason: str = Field(default='统一重算受故障片段影响的分析', min_length=2, max_length=500)
