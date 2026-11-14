from pydantic import BaseModel, Field
class RecalcRetry(BaseModel):
    note: str = Field(default='重试失败的重算任务', max_length=500)
class RecalcApprove(BaseModel):
    note: str = Field(default='批准重算结果并切换分发', max_length=500)
