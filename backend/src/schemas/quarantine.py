from pydantic import BaseModel, Field
class QuarantineInput(BaseModel):
    run: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=2, max_length=500)
class RestoreInput(BaseModel):
    reason: str = Field(min_length=2, max_length=500)
