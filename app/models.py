from pydantic import BaseModel


class ClientCommand(BaseModel):
    action: str
    stream: str
    timestamp: int | None = None
