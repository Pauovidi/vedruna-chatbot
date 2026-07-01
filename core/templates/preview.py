from __future__ import annotations

from pydantic import BaseModel, Field


class TemplatePreviewRequest(BaseModel):
    template_key: str
    sample_data: dict[str, str] = Field(default_factory=dict)
    enabled: bool = False


class TemplatePreviewResult(BaseModel):
    rendered_text: str
    executed_actions: bool = False
    enqueued_messages: bool = False
    sent_messages: bool = False
    reason: str = "preview_only"


def preview_template(request: TemplatePreviewRequest) -> TemplatePreviewResult:
    if not request.enabled:
        return TemplatePreviewResult(
            rendered_text="Template preview is disabled.",
            reason="disabled",
        )
    fields = ", ".join(f"{key}={value}" for key, value in sorted(request.sample_data.items()))
    suffix = f" ({fields})" if fields else ""
    return TemplatePreviewResult(rendered_text=f"Preview {request.template_key}{suffix}")
