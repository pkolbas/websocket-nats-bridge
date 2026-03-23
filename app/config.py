from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    nats_servers: str = "nats://localhost:4222"
    nats_user: str = ""
    nats_password: str = ""
    allowed_streams: str = ""

    @property
    def nats_server_list(self) -> list[str]:
        return [s.strip() for s in self.nats_servers.split(",") if s.strip()]

    @property
    def allowed_stream_set(self) -> set[str]:
        return {s.strip() for s in self.allowed_streams.split(",") if s.strip()}


settings = Settings()
