from __future__ import annotations

from core.tools.schemas import ToolDefinition

BUILTIN_TOOLS: list[ToolDefinition] = [
    ToolDefinition(name="handoff_to_human", description="Request human takeover."),
    ToolDefinition(name="register_timeline_event", description="Add conversation event."),
    ToolDefinition(name="set_conversation_mode", description="Switch bot/human mode."),
    ToolDefinition(name="reset_conversation_state", description="Clear current state."),
    ToolDefinition(name="mark_priority", description="Mark a conversation as priority."),
    ToolDefinition(name="search_knowledge", description="Search client knowledge."),
    ToolDefinition(name="get_business_faq", description="Fetch business FAQ snippet."),
    ToolDefinition(name="get_service_info", description="Fetch service information."),
    ToolDefinition(
        name="request_new_appointment_handoff",
        description="Ask a human to create a new appointment.",
        risk_level="medium",
        required_confirmation=True,
    ),
    ToolDefinition(name="find_existing_appointment", description="Find appointment stub."),
    ToolDefinition(name="propose_reschedule_options", description="Offer reschedule slots."),
    ToolDefinition(
        name="confirm_reschedule",
        description="Confirm appointment reschedule.",
        risk_level="high",
        required_confirmation=True,
        required_flags=["appointments_enabled"],
    ),
    ToolDefinition(
        name="confirm_cancellation",
        description="Confirm appointment cancellation.",
        risk_level="high",
        required_confirmation=True,
        required_flags=["appointments_enabled"],
    ),
    ToolDefinition(name="find_customer", description="Find customer stub."),
    ToolDefinition(
        name="add_customer_note",
        description="Add CRM note.",
        risk_level="medium",
        required_flags=["crm_write_enabled"],
    ),
    ToolDefinition(name="flag_customer_review", description="Flag account for review."),
    ToolDefinition(
        name="register_media_handoff",
        description="Register media for human review.",
    ),
    ToolDefinition(
        name="transcribe_audio_stub",
        description="Audio transcription placeholder.",
    ),
    ToolDefinition(
        name="send_template_message_stub",
        description="Outbound template placeholder.",
        risk_level="medium",
        required_confirmation=True,
        required_flags=["outbound_enabled"],
    ),
    ToolDefinition(
        name="send_reminder_stub",
        description="Outbound reminder placeholder.",
        risk_level="medium",
        required_confirmation=True,
        required_flags=["outbound_enabled"],
    ),
]
