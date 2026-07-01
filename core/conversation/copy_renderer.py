from __future__ import annotations

from pydantic import BaseModel

from core.adapters.vedruna import VEDRUNA_CLIENT_ID
from core.conversation.actions import ConversationAction
from core.conversation.reply_guardrails import adapt_for_channel, sanitize_visible_text
from core.conversation.state_manager import ConversationState
from core.llm.schemas import ToolResult


class RenderedReply(BaseModel):
    text: str
    channel: str
    reply_key: str
    visibility: str = "user_visible"
    forbidden_terms_checked: bool = True
    handoff_notice_sent: bool = False


COPY_BY_KEY = {
    "information_only_ack": (
        "Perfecto, lo dejamos solo como consulta. Te ayudo con informacion sin mover "
        "ninguna cita ni reserva."
    ),
    "cancel_flow_ack": (
        "De acuerdo, no gestiono ninguna cita ni reserva. "
        "Te ayudo solo con lo que necesites saber."
    ),
    "confirm_before_critical_action": (
        "Antes de cambiar o cancelar nada necesito que me lo confirmes claramente."
    ),
    "mudanzas_ask_origin": (
        "Perfecto. Para preparar el presupuesto, dime primero la ciudad de origen."
    ),
    "mudanzas_ask_destination": "Gracias. Ahora dime la ciudad de destino.",
    "mudanzas_ask_date": "Genial. Que fecha aproximada tienes pensada para la mudanza?",
    "mudanzas_price_context": (
        "Para darte un precio fiable necesito origen, destino y algunos detalles "
        "de la mudanza. "
        "Empezamos por la ciudad de origen?"
    ),
    "perros_ask_dates": "Claro. Dime las fechas de entrada y salida y lo miramos con calma.",
    "perros_ask_pet_details": (
        "Gracias. Dime el nombre del perro y si necesita algun cuidado especial."
    ),
    "perros_price_context": (
        "Te puedo orientar, pero para confirmar condiciones necesito fechas y servicio. "
        "Dime primero entrada y salida."
    ),
    "price_contextual": (
        "Para darte una respuesta fiable necesito revisar el contexto y los datos concretos."
    ),
    "correction_ack": "Gracias por aclararlo. Me quedo con la correccion y seguimos desde ahi.",
    "handoff_visible": "Paso tu consulta al equipo para que te contesten lo antes posible.",
    "handoff_visible_success": (
        "He avisado al equipo. Te responderan por aqui lo antes posible."
    ),
    "red_flag_visible_handoff": (
        "Prefiero que esto lo revise el equipo para no darte una informacion incorrecta."
    ),
    "tool_blocked_confirmation_required": "Necesito una confirmacion clara antes de hacerlo.",
    "tool_blocked_visible": (
        "No puedo completar eso todavia. Revisamos primero el dato que falta."
    ),
    "tool_failed_visible": (
        "No he podido completarlo ahora. Lo revisa una persona y te responderemos por aqui."
    ),
    "tool_dry_run_notice": (
        "Lo he dejado preparado como propuesta, pero queda pendiente de validacion."
    ),
    "tool_success_visible": "Listo, queda registrado.",
    "continue_existing_flow": "Te sigo. Dime un detalle mas y lo dejamos encaminado.",
    "fallback_contextual": "Cuentame un poco mas y te ayudo paso a paso.",
}


def render_conversation_reply(
    action: ConversationAction,
    context: ConversationState,
    channel: str,
    tool_results: list[ToolResult] | None = None,
) -> RenderedReply:
    if context.client_id == VEDRUNA_CLIENT_ID:
        from core.adapters.vedruna.copy_renderer import render_vedruna_reply

        return render_vedruna_reply(action, context, channel, tool_results)
    del context, tool_results
    if not action.visible_reply_required:
        return RenderedReply(
            text="",
            channel=channel,
            reply_key=action.reply_key,
            visibility="suppressed",
            handoff_notice_sent=False,
        )
    text = COPY_BY_KEY.get(action.reply_key)
    if text is None and action.visible_handoff_required:
        text = COPY_BY_KEY["handoff_visible"]
    if text is None:
        text = COPY_BY_KEY["fallback_contextual"]
    safe_text = adapt_for_channel(sanitize_visible_text(text), channel)
    return RenderedReply(
        text=safe_text,
        channel=channel,
        reply_key=action.reply_key,
        handoff_notice_sent=action.visible_handoff_required and bool(safe_text),
    )
