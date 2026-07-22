from __future__ import annotations

from datetime import datetime
from typing import Any

from core.adapters.vedruna.domain_schema import (
    Clinic,
    clinic_address,
    clinic_label,
    clinic_open_weekdays_text,
    clinic_phone,
)
from core.conversation.actions import ConversationAction
from core.conversation.copy_renderer import RenderedReply
from core.conversation.reply_guardrails import adapt_for_channel, sanitize_visible_text
from core.conversation.state_manager import ConversationState
from core.llm.schemas import ToolResult


def render_vedruna_reply(
    action: ConversationAction,
    context: ConversationState,
    channel: str,
    tool_results: list[ToolResult] | None = None,
) -> RenderedReply:
    if not action.visible_reply_required:
        return RenderedReply(
            text="",
            channel=channel,
            reply_key=action.reply_key,
            visibility="suppressed",
        )
    tool_result = tool_results[-1] if tool_results else None
    text = _render_text(action.reply_key, context, tool_result, channel)
    safe_text = adapt_for_channel(sanitize_visible_text(text), channel)
    return RenderedReply(
        text=safe_text,
        channel=channel,
        reply_key=action.reply_key,
        handoff_notice_sent=action.visible_handoff_required and bool(safe_text),
    )


def render_vedruna_stream_buffer() -> str:
    """CopyRenderer-owned buffer text for a slow voice transport."""
    return "Un momento, por favor... "


def _render_text(
    reply_key: str,
    context: ConversationState,
    tool_result: ToolResult | None,
    channel: str,
) -> str:
    slots = context.slots
    clinic = slots.get("clinic")
    if reply_key == "vedruna_greeting":
        if channel == "voice":
            return (
                "Hola, soy el asistente virtual de Clinica Madre Vedruna y Clinica "
                "Santa Isabel. Estoy aqui para ayudarte con tu cita. En que puedo ayudarte?"
            )
        return (
            "Hola, soy el asistente virtual de Clinica Madre Vedruna y Clinica "
            "Santa Isabel. Estoy aqui para ayudarte con tu cita. En que puedo ayudarte?"
        )
    if reply_key == "vedruna_ask_clinic":
        return "Claro. Para que clinica quieres la cita: Madre Vedruna o Santa Isabel?"
    if reply_key == "vedruna_ask_service_madre":
        return "En Madre Vedruna atendemos podologia. Es para una cita de podologia?"
    if reply_key == "vedruna_ask_service_santa":
        return (
            "En Santa Isabel atendemos quiropodia, estudio biomecanico, infiltracion, "
            "ecografia u otro problema. Cual necesitas?"
        )
    if reply_key == "vedruna_ask_insurance":
        return "Para Madre Vedruna, vienes por Sanitas, Generali o particular?"
    if reply_key == "vedruna_ask_first_name":
        return "Perfecto. Para continuar, dime tu nombre, por favor."
    if reply_key == "vedruna_ask_last_names":
        return "Gracias. Ahora dime tus apellidos, por favor."
    if reply_key == "vedruna_ask_phone":
        return "Gracias. Dime un telefono de contacto, por favor."
    if reply_key == "vedruna_ask_reason":
        return "Para dejarlo bien anotado, cual es el motivo de la consulta?"
    if reply_key == "vedruna_ask_date":
        return "Que dia o franja te viene mejor para la cita?"
    if reply_key == "vedruna_searching_availability":
        return "Voy a mirar disponibilidad."
    if reply_key == "vedruna_offer_slots":
        return _render_slots(tool_result, channel)
    if reply_key == "vedruna_creating_appointment":
        return "Voy a intentar crear la cita."
    if reply_key == "vedruna_confirmation_required":
        return "Antes de completar esa gestion necesito que me lo confirmes claramente."
    if reply_key == "vedruna_confirm_appointment":
        return _render_confirmation(tool_result)
    if reply_key == "vedruna_create_dry_run_notice":
        return (
            "La cita queda simulada en entorno de prueba. No se ha escrito en el "
            "software real de la clinica."
        )
    if reply_key == "vedruna_rpa_failure":
        return (
            "No he podido completar la gestion ahora. Llama a la clinica para que "
            "lo revisen directamente."
        )
    if reply_key == "vedruna_price_with_clinic":
        return (
            f"Para consultar precios, por favor llama a {clinic_label(clinic)} al "
            f"{clinic_phone(clinic)}. Alli podran informarte segun tu caso."
        )
    if reply_key == "vedruna_price_ask_clinic":
        return (
            "Para consultar precios, dime primero si quieres contactar con Madre "
            "Vedruna o Santa Isabel y te paso el telefono correspondiente."
        )
    if reply_key == "vedruna_urgent_whatsapp":
        return (
            "No puedo valorar urgencias sanitarias por aqui. Puedo iniciar la busqueda "
            "de la cita mas proxima; si necesitas valoracion inmediata, llama directamente "
            "a la clinica."
        )
    if reply_key == "vedruna_unsupported_specialty":
        phone = clinic_phone(clinic or Clinic.MADRE_VEDRUNA.value)
        return (
            "Para traumatologia o psicologia, contacta directamente con Madre Vedruna "
            f"al {phone}."
        )
    if reply_key == "vedruna_service_not_allowed":
        return "Ese servicio no se puede citar desde este asistente para la clinica elegida."
    if reply_key == "vedruna_santa_isabel_particular_only":
        return (
            "Santa Isabel trabaja solo de forma particular. Si quieres usar Sanitas "
            "o Generali, puedo mirar Madre Vedruna."
        )
    if reply_key == "vedruna_faq_hours":
        return (
            "Madre Vedruna abre martes y jueves de 09:30 a 13:30 y de 15:30 a 19:30, "
            "y viernes de 09:00 a 17:00. Santa Isabel abre lunes y miercoles de "
            "09:30 a 13:30 y de 15:30 a 19:30."
        )
    if reply_key == "vedruna_faq_location":
        return (
            "Madre Vedruna esta en Madre Vedruna 14, bajo derecha. Santa Isabel esta "
            "en Avenida Santa Isabel numero 82, local, 50016 Zaragoza."
        )
    if reply_key == "vedruna_faq_services":
        return (
            "En Madre Vedruna puedo citar podologia. En Santa Isabel puedo ayudar con "
            "quiropodia, estudio biomecanico, infiltracion, ecografia u otro problema."
        )
    if reply_key == "vedruna_faq_insurance":
        return (
            "En Madre Vedruna se trabaja con Sanitas, Generali y particular. "
            "En Santa Isabel se trabaja solo de forma particular."
        )
    if reply_key == "vedruna_human_handoff":
        return "Paso tu consulta al equipo para que te contesten lo antes posible."
    if reply_key == "vedruna_voice_transfer":
        return _render_voice_transfer(tool_result, context)
    if reply_key == "vedruna_ask_phone_for_lookup":
        return "Dime el telefono asociado a la cita, por favor."
    if reply_key == "vedruna_lookup_recall":
        return "Voy a buscar tu cita."
    if reply_key == "vedruna_recall_result":
        return _render_recall(tool_result)
    if reply_key == "vedruna_lookup_cancel":
        return "Voy a buscar la cita antes de cancelar nada."
    if reply_key == "vedruna_cancel_confirm_prompt":
        if _is_dry_run_lookup(tool_result):
            return (
                "He simulado la busqueda en entorno de prueba. No se ha consultado "
                "el software real de la clinica ni se cancelara ninguna cita real."
            )
        return "He encontrado una cita. Confirmame claramente si quieres cancelarla."
    if reply_key == "vedruna_cancelled":
        return "La cita se ha cancelado correctamente."
    if reply_key == "vedruna_lookup_reschedule":
        return "Voy a buscar la cita antes de modificarla."
    if reply_key == "vedruna_reschedule_result":
        if _is_dry_run_lookup(tool_result):
            return (
                "He simulado la busqueda en entorno de prueba. Dime la nueva fecha "
                "solo si quieres probar el flujo sin tocar el software real."
            )
        return "He encontrado la cita. Dime la nueva fecha o franja que prefieres."
    if reply_key == "vedruna_rescheduled":
        return "La cita se ha modificado correctamente."
    return "Cuentame un poco mas y te ayudo paso a paso."


def _render_slots(tool_result: ToolResult | None, channel: str) -> str:
    slots = _tool_slots(tool_result)
    if not slots:
        if tool_result and tool_result.data.get("availability_reason") in {
            "clinic_closed_on_requested_day",
            "clinic_closed_on_returned_day",
        }:
            clinic = str(tool_result.data.get("clinic") or "")
            requested_day = tool_result.data.get("requested_weekday")
            if requested_day:
                return (
                    f"En {clinic_label(clinic)} no atendemos los {requested_day}. "
                    f"Tenemos consulta los {clinic_open_weekdays_text(clinic)}. "
                    "Que dia de esos te viene mejor?"
                )
            return (
                f"En {clinic_label(clinic)} solo atendemos los "
                f"{clinic_open_weekdays_text(clinic)}. Que dia te viene mejor?"
            )
        return "No he encontrado huecos para esa preferencia. Probamos con otra franja?"
    first_two = slots[:2] if channel == "voice" else slots[:3]
    parts = []
    for index, slot in enumerate(first_two, start=1):
        start = _format_datetime(slot.get("start"))
        parts.append(f"Opcion {index}: {start}")
    qualifier = (
        "opciones simuladas de prueba"
        if _is_dry_run_lookup(tool_result)
        else "opciones reales disponibles"
    )
    if channel == "voice":
        return f"Tengo estas {qualifier}: {'; '.join(parts)}. Cual prefieres?"
    return f"Tengo estas {qualifier}:\n" + "\n".join(parts)


def _render_confirmation(tool_result: ToolResult | None) -> str:
    if (
        tool_result is None
        or tool_result.status != "success"
        or tool_result.data.get("ok") is not True
        or tool_result.data.get("dry_run") is True
    ):
        return (
            "No he podido confirmar la cita ahora. Llama a la clinica para que "
            "lo revisen directamente."
        )
    data = tool_result.data if tool_result else {}
    start = _format_datetime(data.get("start"))
    clinic = clinic_label(data.get("clinic"))
    return f"\U0001F4C5 Confirmamos tu cita el {start} en la clinica {clinic}."


def _render_recall(tool_result: ToolResult | None) -> str:
    data = tool_result.data if tool_result else {}
    if data.get("dry_run") is True:
        return (
            "Consulta simulada en entorno de prueba. No se ha consultado el software "
            "real de la clinica."
        )
    appointment = data.get("appointment") if isinstance(data.get("appointment"), dict) else None
    if not appointment:
        return "No he encontrado una cita con esos datos."
    start = _format_datetime(appointment.get("start"))
    if appointment.get("dateReadable") and appointment.get("time"):
        start = f"{appointment.get('dateReadable')} a las {appointment.get('time')}"
    clinic = appointment.get("clinic")
    address = appointment.get("address") or clinic_address(clinic)
    return (
        f"Tienes una cita el {start} en la clinica {clinic_label(clinic)}, "
        f"en {address}."
    )


def _tool_slots(tool_result: ToolResult | None) -> list[dict[str, Any]]:
    if not tool_result:
        return []
    slots = tool_result.data.get("slots")
    return slots if isinstance(slots, list) else []


def _is_dry_run_lookup(tool_result: ToolResult | None) -> bool:
    return bool(tool_result and tool_result.data.get("dry_run") is True)


def _format_datetime(value: Any) -> str:
    if not value:
        return "la fecha indicada"
    if not isinstance(value, str):
        return str(value)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime("%d/%m/%Y a las %H:%M")


def _render_voice_transfer(
    tool_result: ToolResult | None,
    context: ConversationState,
) -> str:
    data = tool_result.data if tool_result else {}
    phone = clinic_phone(context.slots.get("clinic") or Clinic.MADRE_VEDRUNA.value)
    if data.get("transfer_enabled") is False:
        return (
            "Necesitas hablar con la clinica. No voy a confirmar una transferencia real "
            f"desde este entorno; llama al {phone} para que te atiendan directamente."
        )
    return "Te paso con la clinica para que puedan atenderte directamente."
