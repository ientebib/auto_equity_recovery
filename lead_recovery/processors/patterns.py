# -*- coding: utf-8 -*-
"""Centralized repository for regex patterns and keyword lists used by processors.

This module stores string constants for regex patterns and lists of strings
for keywords and phrases to promote maintainability and avoid duplication
across different processors.

Processors should import these constants and compile regex patterns as needed.
"""

# From lead_recovery/processors/handoff.py
HANDOFF_INVITATION_REGEX_PATTERN = (
    r"Estas a un paso de la aprobacion de tu prestamo personal|"
    r"un paso de la aprobacion|"
    r"Esta oferta es por tiempo limitado|"
    r"Completa el proceso ahora|"
    r"asegura tu prestamo en minutos|"
    r"No pierdas la oportunidad"
)

HANDOFF_ACCEPTANCE_PATTERNS = [
    r"si(,)?\s+(quisiera|quiero)",
    r"acepto.*oferta",
    r"(quisiera|quiero|gustaria).*mas\s+informacion",
    r"me\s+interesa",
    r"(quisiera|quiero|gustaria).*saber\s+mas",
    r"continuar.*proceso",
    r"^si$",
    r"^si\s+por\s+favor$"
]

HANDOFF_DECLINE_PATTERNS = [
    r"no(,)?\s+(quiero|quisiera|me\s+interesa)",
    r"no\s+gracias",
    r"rechaz[oa]",
    r"^no$"
]

HANDOFF_COMPLETION_PHRASES = [
    r"tu\s+solicitud\s+ha\s+sido\s+enviada",
    r"tu\s+solicitud\s+ha\s+sido\s+recibida",
    r"tu\s+solicitud\s+ha\s+sido\s+procesada",
    r"gracias\s+por\s+completar\s+el\s+proceso",
    r"hemos\s+recibido\s+tu\s+solicitud"
]

# From lead_recovery/processors/human_transfer.py
HUMAN_TRANSFER_PATTERNS = [
    r"transferirte con un asesor humano",
    r"conectarte con un agente humano",
    r"hablar con un asesor",
    r"comunicarte con un asesor",
    r"transferir con un ejecutivo",
    r"un momento, estoy teniendo problemas",
    r"un supervisor te asistirá",
    r"transferirte con una persona"
]

# From lead_recovery/processors/template.py
RECOVERY_TEMPLATE_PHRASES = [
    "préstamo por tu auto",
    "oferta pre aprobada",
    "aprovecha tu oferta",
    "espera de que nos proporciones tus documentos",
    "template:"
]

# From lead_recovery/processors/validation.py
PRE_VALIDACION_PHRASES = [
    "antes de continuar, necesito confirmar tres detalles importantes sobre tu auto",
    "necesito confirmar algunos detalles sobre tu auto y tu elegibilidad para el credito"
]
