"""Immutable execution provenance, never an authentication or permission grant."""

from enum import StrEnum
from typing import Annotated, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator


TenantID = Annotated[StrictInt, Field(ge=1, le=9223372036854775807)]
MachineID = Annotated[StrictStr, Field(min_length=1, max_length=128,
                                     pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*\z")]
CorrelationID = Annotated[StrictStr, Field(min_length=1, max_length=64,
                                         pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*\z")]


class PrincipalType(StrEnum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    AGENT = "AGENT"
    WORKFLOW = "WORKFLOW"
    INTEGRATION = "INTEGRATION"


class ActorReference(BaseModel):
    """One bounded typed authority reference; no recursive delegation graph."""

    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")
    principal_type: PrincipalType
    actor_id: TenantID | MachineID

    @model_validator(mode="after")
    def actor_matches_type(self) -> Self:
        if self.principal_type == PrincipalType.USER:
            if type(self.actor_id) is not int:
                raise ValueError("USER requires an integer user identifier.")
        elif type(self.actor_id) is not str:
            raise ValueError("Machine actors require a stable string identifier.")
        return self


class ExecutionPrincipal(ActorReference):
    organization_id: TenantID
    correlation_id: CorrelationID = Field(default_factory=lambda: uuid4().hex)
    delegated_by: ActorReference | None = None
    workflow_run_id: MachineID | None = None
    integration_id: MachineID | None = None
    agent_id: MachineID | None = None

    @model_validator(mode="after")
    def provenance_matches_type(self) -> Self:
        required = {PrincipalType.AGENT: self.agent_id,
                    PrincipalType.WORKFLOW: self.workflow_run_id,
                    PrincipalType.INTEGRATION: self.integration_id}
        if self.principal_type in required and required[self.principal_type] != self.actor_id:
            raise ValueError("Machine actor and its required provenance identifier must match.")
        if self.principal_type == PrincipalType.USER and any(
            value is not None for value in (self.delegated_by, self.workflow_run_id,
                                           self.integration_id, self.agent_id)
        ):
            raise ValueError("Direct USER principals cannot claim machine/delegated provenance.")
        return self

    @classmethod
    def for_user(cls, user_id: int, organization_id: int, *, correlation_id: str | None = None) -> Self:
        return cls(principal_type=PrincipalType.USER, actor_id=user_id,
                   organization_id=organization_id,
                   correlation_id=correlation_id if correlation_id is not None else uuid4().hex)

    @classmethod
    def for_system(cls, system_id: str, organization_id: int, *,
                   delegated_by: ActorReference | None = None, correlation_id: str | None = None) -> Self:
        return cls(principal_type=PrincipalType.SYSTEM, actor_id=system_id,
                   organization_id=organization_id, delegated_by=delegated_by,
                   correlation_id=correlation_id if correlation_id is not None else uuid4().hex)

    @classmethod
    def for_agent(cls, agent_id: str, organization_id: int, *,
                  delegated_by: ActorReference | None = None, correlation_id: str | None = None,
                  workflow_run_id: str | None = None, integration_id: str | None = None) -> Self:
        return cls(principal_type=PrincipalType.AGENT, actor_id=agent_id, agent_id=agent_id,
                   organization_id=organization_id, delegated_by=delegated_by,
                   workflow_run_id=workflow_run_id, integration_id=integration_id,
                   correlation_id=correlation_id if correlation_id is not None else uuid4().hex)

    @classmethod
    def for_workflow(cls, workflow_run_id: str, organization_id: int, *,
                     delegated_by: ActorReference | None = None, correlation_id: str | None = None) -> Self:
        return cls(principal_type=PrincipalType.WORKFLOW, actor_id=workflow_run_id,
                   workflow_run_id=workflow_run_id, organization_id=organization_id,
                   delegated_by=delegated_by,
                   correlation_id=correlation_id if correlation_id is not None else uuid4().hex)

    @classmethod
    def for_integration(cls, integration_id: str, organization_id: int, *,
                        delegated_by: ActorReference | None = None, correlation_id: str | None = None) -> Self:
        return cls(principal_type=PrincipalType.INTEGRATION, actor_id=integration_id,
                   integration_id=integration_id, organization_id=organization_id,
                   delegated_by=delegated_by,
                   correlation_id=correlation_id if correlation_id is not None else uuid4().hex)

    def to_json(self) -> str:
        """Stable field order, primitives only; no transport credentials."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, value: str) -> Self:
        """Decode shape only. Trusted ingress must authenticate provenance separately."""
        return cls.model_validate_json(value)
