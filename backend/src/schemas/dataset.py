from pydantic import BaseModel, Field
class DatasetInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    source: str = Field(default='manual.json', max_length=200)
    records: list[dict] = Field(min_length=5, max_length=5000)
class ExclusionInput(BaseModel):
    run: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=2, max_length=500)
class ExclusionBatchInput(BaseModel):
    runs: list[str] = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=2, max_length=500)
