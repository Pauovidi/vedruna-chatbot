from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    openai_transcribe_model: str | None = Field(
        default=None, alias="OPENAI_TRANSCRIBE_MODEL"
    )
    openai_temperature: float = Field(default=0.3, alias="OPENAI_TEMPERATURE")
    openai_timeout_seconds: int = Field(default=12, alias="OPENAI_TIMEOUT_SECONDS")
    conversational_reply_enabled: bool = Field(
        default=True, alias="CONVERSATIONAL_REPLY_ENABLED"
    )
    conversational_reply_shadow: bool = Field(
        default=False, alias="CONVERSATIONAL_REPLY_SHADOW"
    )
    conversational_reply_shadow_call_enabled: bool = Field(
        default=False, alias="CONVERSATIONAL_REPLY_SHADOW_CALL_ENABLED"
    )
    release_label: str | None = Field(default=None, alias="RELEASE_LABEL")
    port: int = Field(default=8080, alias="PORT")
    public_base_url: str = Field(
        default="https://chatbot.example.com", alias="PUBLIC_BASE_URL"
    )
    voice_ws_url: str = Field(
        default="wss://chatbot.example.com/webhook/voice/conversationrelay/ws",
        alias="VOICE_WS_URL",
    )
    twilio_account_sid: str | None = Field(default=None, alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str | None = Field(default=None, alias="TWILIO_AUTH_TOKEN")
    twilio_whatsapp_from: str | None = Field(default=None, alias="TWILIO_WHATSAPP_FROM")
    twilio_voice_number: str | None = Field(default=None, alias="TWILIO_VOICE_NUMBER")
    twilio_validate_signature: bool = Field(
        default=False, alias="TWILIO_VALIDATE_SIGNATURE"
    )
    twilio_whatsapp_reply_mode: str = Field(
        default="twiml", alias="TWILIO_WHATSAPP_REPLY_MODE"
    )
    conversation_relay_tts_provider: str = Field(
        default="ElevenLabs", alias="CONVERSATION_RELAY_TTS_PROVIDER"
    )
    conversation_relay_voice: str | None = Field(
        default=None, alias="CONVERSATION_RELAY_VOICE"
    )
    conversation_relay_language: str = Field(
        default="es-ES", alias="CONVERSATION_RELAY_LANGUAGE"
    )
    conversation_relay_transcription_language: str = Field(
        default="es-ES", alias="CONVERSATION_RELAY_TRANSCRIPTION_LANGUAGE"
    )
    conversation_relay_welcome_greeting: str = Field(
        default=(
            "Hola, soy el asistente de Clinica Madre Vedruna y Clinica Santa Isabel. "
            "En que puedo ayudarte?"
        ),
        alias="CONVERSATION_RELAY_WELCOME_GREETING",
    )
    voice_transfer_enabled: bool = Field(default=False, alias="VOICE_TRANSFER_ENABLED")
    admin_panel_api_key: str | None = Field(default=None, alias="ADMIN_PANEL_API_KEY")
    rpa_base_url: str = Field(
        default="https://vedruna-rpa-rpa.ddxo6v.easypanel.host",
        alias="RPA_BASE_URL",
    )
    rpa_api_key: str | None = Field(default=None, alias="RPA_API_KEY")
    rpa_dry_run: bool = Field(default=True, alias="RPA_DRY_RUN")
    rpa_timeout_ms: int = Field(default=12000, alias="RPA_TIMEOUT_MS")
    clinic_madre_vedruna_phone: str = Field(
        default="976795117", alias="CLINIC_MADRE_VEDRUNA_PHONE"
    )
    clinic_santa_isabel_phone: str = Field(
        default="976582768", alias="CLINIC_SANTA_ISABEL_PHONE"
    )
    pii_masking_enabled: bool = Field(default=True, alias="PII_MASKING_ENABLED")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @computed_field
    @property
    def store_type(self) -> str:
        if self.database_url:
            if self.database_url.startswith("postgres"):
                return "postgres"
            if self.database_url.startswith("sqlite"):
                return "sqlite"
        return "memory"

    @computed_field
    @property
    def persistence_durable(self) -> bool:
        return self.store_type == "postgres"

    @computed_field
    @property
    def ephemeral_store(self) -> bool:
        return self.store_type == "memory"

    def assert_production_ready(self) -> None:
        if self.app_env == "production" and not self.persistence_durable:
            raise RuntimeError("APP_ENV=production requires a durable Postgres DATABASE_URL")

    def safe_health(self) -> dict[str, object]:
        return {
            "env": self.app_env,
            "store_type": self.store_type,
            "database_url_present": bool(self.database_url),
            "persistence_durable": self.persistence_durable,
            "ephemeral_store": self.ephemeral_store,
            "llm_provider": "openai",
            "openai_api_key_present": bool(self.openai_api_key),
            "model": self.openai_model,
            "production_ready": not (
                self.app_env == "production" and not self.persistence_durable
            ),
            "release_label": self.release_label,
            "port": self.port,
            "public_base_url_present": bool(self.public_base_url),
            "voice_ws_url_present": bool(self.voice_ws_url),
            "twilio_account_sid_present": bool(self.twilio_account_sid),
            "twilio_auth_token_present": bool(self.twilio_auth_token),
            "twilio_validate_signature": self.twilio_validate_signature,
            "conversation_relay_tts_provider_present": bool(
                self.conversation_relay_tts_provider
            ),
            "conversation_relay_voice_present": bool(self.conversation_relay_voice),
            "voice_transfer_enabled": self.voice_transfer_enabled,
            "rpa_base_url_present": bool(self.rpa_base_url),
            "rpa_api_key_present": bool(self.rpa_api_key),
            "rpa_dry_run": self.rpa_dry_run,
            "admin_panel_api_key_present": bool(self.admin_panel_api_key),
            "pii_masking_enabled": self.pii_masking_enabled,
        }


ROOT_DIR = Path(__file__).resolve().parents[1]


@lru_cache
def get_settings() -> Settings:
    return Settings()
