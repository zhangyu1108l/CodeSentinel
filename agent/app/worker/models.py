from pydantic import BaseModel


class TaskMessage(BaseModel):
    taskId: int
    owner: str
    repo: str
    prNumber: int
    commitSha: str