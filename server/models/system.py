"""System-level API models."""

from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field


HANDSHAKE_REQUEST_SCHEMA = "zotero-agents.skillrunner-handshake.request.v1"
HANDSHAKE_RESPONSE_SCHEMA = "zotero-agents.skillrunner-handshake.response.v1"
BACKEND_NAME = "Skill-Runner"
PROTOCOL_SKILLRUNNER_JOB_V1 = "skillrunner.job.v1"
PROTOCOL_SKILLRUNNER_SEQUENCE_V1 = "skillrunner.sequence.v1"


class SystemHandshakeClient(BaseModel):
    """Client identity submitted with a handshake request."""

    name: str
    version: str


class SystemHandshakeRequest(BaseModel):
    """Handshake request used by Zotero Agents clients."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: str = Field(default=HANDSHAKE_REQUEST_SCHEMA, alias="schema")
    client: SystemHandshakeClient
    requested_protocols: List[str] = Field(default_factory=list)


class SystemHandshakeBackend(BaseModel):
    """Backend identity returned by the handshake endpoint."""

    name: str = BACKEND_NAME
    version: str


class SystemProtocolCapability(BaseModel):
    """Support state for one stable protocol id."""

    supported: bool


class SystemHandshakeResponse(BaseModel):
    """Handshake response with protocol capabilities."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: str = Field(default=HANDSHAKE_RESPONSE_SCHEMA, alias="schema")
    backend: SystemHandshakeBackend
    protocols: Dict[str, SystemProtocolCapability] = Field(default_factory=dict)
