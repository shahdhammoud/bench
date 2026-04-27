from pydantic import BaseModel, Field
from typing import Optional


class ModuleInfo(BaseModel):
    name: str
    purpose: str
    interfaces: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    key_classes: list[str] = Field(default_factory=list)
    key_functions: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class APIEndpoint(BaseModel):
    path: str
    method: str
    description: str
    request_body: Optional[str] = None
    response: Optional[str] = None
    auth_required: bool = False


class GeneratedDocs(BaseModel):
    project_name: str
    project_goal: str
    functional_requirements: list[str] = Field(default_factory=list)
    non_functional_requirements: list[str] = Field(default_factory=list)
    modules: list[ModuleInfo] = Field(default_factory=list)
    api_endpoints: list[APIEndpoint] = Field(default_factory=list)
    async_events: list[str] = Field(default_factory=list)
    guidelines: list[str] = Field(default_factory=list)


class InspectFilesOutput(BaseModel):
    modules: list[dict] = Field(default_factory=list)


class IdentifyContractsOutput(BaseModel):
    endpoints: list[dict] = Field(default_factory=list)
    async_events: list[str] = Field(default_factory=list)


class InferRequirementsOutput(BaseModel):
    project_name: str = ""
    project_goal: str = ""
    functional_requirements: list[str] = Field(default_factory=list)
    non_functional_requirements: list[str] = Field(default_factory=list)


class ModuleDocOutput(BaseModel):
    name: str = ""
    purpose: str = ""
    interfaces: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    key_classes: list[str] = Field(default_factory=list)
    key_functions: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class CriticOutput(BaseModel):
    score: float = 5.0
    problems: list[str] = Field(default_factory=list)
