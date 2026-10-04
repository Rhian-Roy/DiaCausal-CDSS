"""Shared base: every model forbids unknown fields and carries schema_version "1.0"."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = "1.0"

OptionName = Literal["SGLT2i", "DPP4i", "SU"]
OPTION_NAMES = ("SGLT2i", "DPP4i", "SU")


class V1(BaseModel):
    """Base of every v1 model. Unknown fields are rejected (never silently dropped); `schema_version` is
    always "1.0" (optional on input, always written on output; AskRequestV1 requires it)."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = SCHEMA_VERSION
