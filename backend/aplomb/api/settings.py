"""Validated configuration; constructing Settings performs no network I/O."""

import os
from typing import Literal, Mapping

from pydantic import BaseModel, Field, model_validator

from aplomb.contracts.base import DataVersion, ISODate
from aplomb.contracts.catalog import FeatureFlag


class Settings(BaseModel):
    environment: Literal["local", "aws"] = "local"
    region: str = "us-east-1"
    data_version: DataVersion | Literal["unconfigured"] = "unconfigured"
    data_as_of: ISODate = "2026-11-12"
    data_dir: str | None = None
    data_bucket: str | None = None
    data_prefix: str = ""
    profiles_table: str | None = None
    runs_table: str | None = None
    cache_table: str | None = None
    worker_function: str | None = None
    model_strong: str | None = None
    model_fast: str | None = None
    guardrail_id: str | None = None
    guardrail_version: str | None = None
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    source_user_agent: str | None = None
    features: dict[FeatureFlag, bool] = Field(
        default_factory=lambda: {flag: False for flag in FeatureFlag}
    )
    run_target_seconds: int = Field(default=90, gt=0)
    run_hard_seconds: int = Field(default=180, gt=0)
    max_revise: int = Field(default=2, ge=0, le=2)
    max_llm_calls: int = Field(default=12, ge=0)
    max_research_calls: int = Field(default=12, ge=0)
    local_state_file: str | None = None
    max_body_bytes: int = Field(default=262144, ge=1024)
    lease_seconds: int = Field(default=30, gt=0)

    @model_validator(mode="after")
    def validate_configuration(self):
        self.features = {flag: self.features.get(flag, False) for flag in FeatureFlag}
        if "*" in self.allowed_origins:
            raise ValueError("CORS requires explicit origins")
        if self.run_target_seconds > self.run_hard_seconds:
            raise ValueError("run target exceeds hard budget")
        if self.environment == "aws":
            required = (
                "data_bucket",
                "profiles_table",
                "runs_table",
                "cache_table",
                "worker_function",
                "data_version",
                "source_user_agent",
            )
            if missing := [name for name in required if not getattr(self, name)]:
                raise ValueError(f"AWS settings missing: {', '.join(missing)}")
            if self.data_version == "unconfigured":
                raise ValueError("AWS requires a pinned data version")
        if self.features[FeatureFlag.GUARDRAILS] and not (
            self.guardrail_id and self.guardrail_version
        ):
            raise ValueError("guardrails require ID and version")
        return self

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        values: dict = {}
        names = {
            name: f"APLOMB_{name.upper()}"
            for name in cls.model_fields
            if name not in {"features", "environment", "region"}
        }
        names.update(environment="APLOMB_ENV", region="AWS_REGION")
        for name, key in names.items():
            if key in env:
                values[name] = env[key]
        if "allowed_origins" in values:
            values["allowed_origins"] = [
                s.strip() for s in values["allowed_origins"].split(",") if s.strip()
            ]
        flags = {}
        for flag in FeatureFlag:
            key = f"APLOMB_FEATURE_{flag.value.upper()}"
            raw = env.get(key, "false").lower()
            if raw not in {"true", "false", "1", "0"}:
                raise ValueError(f"{key} must be true or false")
            flags[flag] = raw in {"true", "1"}
        values["features"] = flags
        return cls.model_validate(values)
