import json
import re
from datetime import datetime
import unicodedata
import logging

logger = logging.getLogger(__name__)

# Helper function to strip accents from a string
def strip_accents(text: str) -> str:
    if not isinstance(text, str):
        return ""
    try:
        # Normalize to NFD (Normalization Form D) to separate base characters from diacritics
        nfd_form = unicodedata.normalize('NFD', text)
        # Filter out non-spacing marks (Mn category), which are the diacritics
        return "".join(c for c in nfd_form if unicodedata.category(c) != 'Mn')
    except TypeError:
        return ""

def analyze_diana_conversation(conversation_messages: list) -> dict:
    """
    Analyzes a conversation to detect a specific bot offer message and the user's subsequent response.
    Accents in the bot message are normalized for robust matching.

    Args:
        conversation_messages: A list of dictionaries, where each dictionary represents a message
                               and contains 'msg_from', 'message', and 'creation_time' keys.
                               Messages are expected to be sorted by creation_time.

    Returns:
        A dictionary containing:
            'offer_message_detected': (bool) True if the offer message was found.
            'user_response_to_offer': (str|None) 'Me interesa', 'de momento no', 'ignored', or None.
            'handoff_reached': (bool) True if handoff invitation was sent to user.
            'handoff_response': (str) 'STARTED_HANDOFF', 'DECLINED_HANDOFF', 'IGNORED_HANDOFF', or 'NOT_APPLICABLE'.
            'handoff_finalized': (bool) True if handoff process was completed, False otherwise.
            'handoff_stall_reason': (str) Explanation of why the handoff process stalled (if applicable).
    """
    # Initialize result dictionary with default values
    result = {
        "offer_message_detected": False,
        "user_response_to_offer": None,
        "handoff_reached": False,
        "handoff_response": "NOT_APPLICABLE",
        "handoff_finalized": False,
        "handoff_stall_reason": ""
    }
    
    # Ensure messages are sorted by creation_time
    # For robustness, actual datetime conversion and sorting might be needed if format varies
    
    # ---- STEP 1: DETECT OFFER MESSAGE AND USER RESPONSE ----
    
    # Regex to detect the bot's offer message.
    # Defined with unaccented versions of potentially accented words
    offer_template_pattern = re.compile(
        r"Template:\n\n¡Hola .*! 👋 Gracias por confiar en Kuna Capital.\n\n"
        r"\*¡Tienes una oferta preaprobada para tu prestamo personal con Garantia de hasta \$[^!]*!\* 🎉\n\n"
        r"Queremos acompanarte en este proceso para que accedas a todos los beneficios cuanto antes.\n\n"
        r"Para acompanarte y resolver todas tus dudas, por favor selecciona una de las siguientes opciones 👇"
    )
    
    offer_message_index = -1
    for i, msg in enumerate(conversation_messages):
        if msg.get('msg_from') == 'bot':
            message_content = msg.get('message', '')
            stripped_message_content = strip_accents(message_content)

            if offer_template_pattern.search(stripped_message_content):
                result["offer_message_detected"] = True
                offer_message_index = i
                break # Interested in the first occurrence

    if result["offer_message_detected"]:
        result["user_response_to_offer"] = "ignored" # Default if offer is detected

        if offer_message_index + 1 < len(conversation_messages):
            next_message = conversation_messages[offer_message_index + 1]
            if next_message.get('msg_from') == 'user':
                try:
                    # User message is expected to be a JSON string with a "button" key
                    raw_user_message = next_message.get('message', '{}')
                    user_message_data = json.loads(raw_user_message)
                    button_clicked = user_message_data.get('button')

                    if button_clicked == "Me interesa":
                        result["user_response_to_offer"] = "Me interesa"
                    elif button_clicked == "de momento no": # Assuming this is the negative response
                        result["user_response_to_offer"] = "de momento no"
                    # If button_clicked is something else, it remains "ignored"
                except (json.JSONDecodeError, AttributeError):
                    # If message is not valid JSON or other issues, consider "ignored"
                    pass
    
    # ---- STEP 2: DETECT HANDOFF INVITATION ----
    
    # Only proceed with handoff analysis if user responded with "Me interesa"
    if result["user_response_to_offer"] == "Me interesa":
        # Debug: Log phone number and message count
        phone = conversation_messages[0].get('cleaned_phone_number', 'unknown')
        logger.info(f"Phone {phone} clicked 'Me interesa'. Analyzing {len(conversation_messages)} messages for handoff invitation.")
        
        # Regex to detect handoff invitation - using a significant portion of text without emojis
        handoff_invitation_pattern = re.compile(
            r"Estas a un paso de la aprobacion de tu prestamo personal|"
            r"un paso de la aprobacion|"
            r"Esta oferta es por tiempo limitado|"
            r"Completa el proceso ahora|"
            r"asegura tu prestamo en minutos|"
            r"No pierdas la oportunidad", 
            re.IGNORECASE
        )
        
        handoff_invitation_index = -1
        for i, msg in enumerate(conversation_messages):
            if msg.get('msg_from') == 'bot' and i > offer_message_index:
                message_content = msg.get('message', '')
                stripped_message_content = strip_accents(message_content)
                
                # Debug: Log message to see if it contains handoff invitation
                logger.debug(f"Checking message {i} for handoff invitation: {stripped_message_content[:100]}...")
                
                if handoff_invitation_pattern.search(stripped_message_content):
                    result["handoff_reached"] = True
                    handoff_invitation_index = i
                    logger.info(f"Handoff invitation found in message {i} for phone {phone}")
                    break
        
        # If we didn't find a handoff invitation, log that too
        if not result["handoff_reached"]:
            logger.info(f"No handoff invitation found for phone {phone} after 'Me interesa'")
        
        # ---- STEP 3: DETECT HANDOFF RESPONSE ----
        
        if result["handoff_reached"]:
            result["handoff_response"] = "IGNORED_HANDOFF"  # Default if handoff is detected
            
            if handoff_invitation_index + 1 < len(conversation_messages):
                next_message = conversation_messages[handoff_invitation_index + 1]
                if next_message.get('msg_from') == 'user':
                    try:
                        # User message is expected to be a JSON string with a "button" key
                        raw_user_message = next_message.get('message', '{}')
                        logger.debug(f"Checking handoff response: {raw_user_message}")
                        user_message_data = json.loads(raw_user_message)
                        button_clicked = user_message_data.get('button')
                        
                        if button_clicked == "Empezar":
                            result["handoff_response"] = "STARTED_HANDOFF"
                            logger.info(f"User {phone} clicked 'Empezar' to start handoff")
                        elif button_clicked == "De momento no":
                            result["handoff_response"] = "DECLINED_HANDOFF"
                            logger.info(f"User {phone} clicked 'De momento no' to decline handoff")
                        # If button_clicked is something else, it remains "IGNORED_HANDOFF"
                    except (json.JSONDecodeError, AttributeError):
                        # If message is not valid JSON or other issues, consider "IGNORED_HANDOFF"
                        pass
            
            # ---- STEP 4: DETECT HANDOFF FINALIZATION ----
            
            # Only check for handoff finalization if user started the handoff
            if result["handoff_response"] == "STARTED_HANDOFF":
                # Regex patterns to detect handoff finalization
                handoff_finalized_patterns = [
                    re.compile(r"Hemos finalizado el proceso de onboarding", re.IGNORECASE),
                    re.compile(r"Tu perfil ha sido aprobado", re.IGNORECASE),
                    re.compile(r"Felicidades.*tu prestamo ha sido aprobado", re.IGNORECASE),
                    re.compile(r"Tu prestamo ha sido procesado exitosamente", re.IGNORECASE)
                ]
                
                # Check messages after handoff started
                for i, msg in enumerate(conversation_messages):
                    if msg.get('msg_from') == 'bot' and i > handoff_invitation_index:
                        message_content = msg.get('message', '')
                        stripped_message_content = strip_accents(message_content)
                        
                        for pattern in handoff_finalized_patterns:
                            if pattern.search(stripped_message_content):
                                result["handoff_finalized"] = True
                                logger.info(f"Handoff finalization detected for phone {phone}")
                                break
                        
                        if result["handoff_finalized"]:
                            break
                
                # ---- STEP 5: DETERMINE STALL REASON (if not finalized) ----
                
                if not result["handoff_finalized"]:
                    # Default stall reason
                    result["handoff_stall_reason"] = "PROCESO_INCOMPLETO"
                    
                    # Check for common stall patterns
                    stall_patterns = {
                        "PROBLEMAS_TECNICOS": re.compile(r"(error|falla|no puedo|no funciona|problema tecnico)", re.IGNORECASE),
                        "SOLICITO_AYUDA": re.compile(r"(necesito ayuda|ayudame|no entiendo)", re.IGNORECASE),
                        "CAMBIO_OPINION": re.compile(r"(ya no quiero|cambie de opinion|lo pensare|mejor despues)", re.IGNORECASE),
                        "DOCUMENTOS_PENDIENTES": re.compile(r"(no tengo los documentos|falta|despues subo)", re.IGNORECASE),
                    }
                    
                    # Check user messages after handoff started
                    for i, msg in enumerate(conversation_messages):
                        if msg.get('msg_from') == 'user' and i > handoff_invitation_index:
                            message_content = msg.get('message', '')
                            
                            for reason, pattern in stall_patterns.items():
                                if pattern.search(message_content):
                                    result["handoff_stall_reason"] = reason
                                    logger.info(f"Stall reason detected for phone {phone}: {reason}")
                                    break
                            
                            if result["handoff_stall_reason"] != "PROCESO_INCOMPLETO":
                                break

    return result

# Example usage section
if __name__ == '__main__':
    # Example Usage with handoff scenarios
    sample_handoff_started = [
        {
            "cleaned_phone_number": "8442656544",
            "creation_time": "2025-05-06 19:31:01.151000 UTC",
            "msg_from": "bot",
            "operator_alias": None,
            "message": "Template:\n\n¡Hola *Juan salomé lópez limón*! 👋 Gracias por confiar en Kuna Capital.\n\n*¡Tienes una oferta preaprobada para tu préstamo personal con Garantía de hasta $85,212.93!* 🎉\n\nQueremos acompañarte en este proceso para que accedas a todos los beneficios cuanto antes.\n\nPara acompañarte y resolver todas tus dudas, por favor selecciona una de las siguientes opciones 👇"
        },
        {
            "cleaned_phone_number": "8442656544",
            "creation_time": "2025-05-06 19:31:29.868000 UTC",
            "msg_from": "user",
            "operator_alias": None,
            "message": "{\"button\":\"Me interesa\",\"entities\":\"{}\",\"intent\":\"RuleBuilder:kavakcapital-qok4a8go95@b.m-1739896840354\"}"
        },
        {
            "cleaned_phone_number": "8442656544",
            "creation_time": "2025-05-06 19:32:01.151000 UTC",
            "msg_from": "bot",
            "operator_alias": None,
            "message": "¡Estás a un paso de la aprobación de tu préstamo personal! 🙌\nEsta oferta es por tiempo limitado, así que no esperes más.\nCompleta el proceso ahora, con tu información personal, y asegura tu préstamo en minutos 💸\n¡No pierdas la oportunidad! 🚀"
        },
        {
            "cleaned_phone_number": "8442656544",
            "creation_time": "2025-05-06 19:32:29.868000 UTC",
            "msg_from": "user",
            "operator_alias": None,
            "message": "{\"button\":\"Empezar\",\"entities\":\"{}\",\"intent\":\"start-handoff\"}"
        }
    ]
    
    sample_handoff_declined = [
        {
            "cleaned_phone_number": "1234567890",
            "creation_time": "2025-05-07 10:00:00.000000 UTC",
            "msg_from": "bot",
            "message": "Template:\n\n¡Hola *Maria Rodriguez*! 👋 Gracias por confiar en Kuna Capital.\n\n*¡Tienes una oferta preaprobada para tu préstamo personal con Garantía de hasta $50,000.00!* 🎉\n\nQueremos acompañarte en este proceso para que accedas a todos los beneficios cuanto antes.\n\nPara acompañarte y resolver todas tus dudas, por favor selecciona una de las siguientes opciones 👇"
        },
        {
            "cleaned_phone_number": "1234567890",
            "creation_time": "2025-05-07 10:00:30.000000 UTC",
            "msg_from": "user",
            "message": "{\"button\":\"Me interesa\",\"entities\":\"{}\",\"intent\":\"some_intent_here\"}"
        },
        {
            "cleaned_phone_number": "1234567890",
            "creation_time": "2025-05-07 10:01:00.000000 UTC",
            "msg_from": "bot",
            "message": "¡Estás a un paso de la aprobación de tu préstamo personal! 🙌\nEsta oferta es por tiempo limitado, así que no esperes más.\nCompleta el proceso ahora, con tu información personal, y asegura tu préstamo en minutos 💸\n¡No pierdas la oportunidad! 🚀"
        },
        {
            "cleaned_phone_number": "1234567890",
            "creation_time": "2025-05-07 10:01:30.000000 UTC",
            "msg_from": "user",
            "message": "{\"button\":\"De momento no\",\"entities\":\"{}\",\"intent\":\"decline-handoff\"}"
        }
    ]
    
    sample_handoff_ignored = [
        {
            "cleaned_phone_number": "1112223333",
            "creation_time": "2025-05-07 11:00:00.000000 UTC",
            "msg_from": "bot",
            "message": "Template:\n\n¡Hola *Carlos Santana*! 👋 Gracias por confiar en Kuna Capital.\n\n*¡Tienes una oferta preaprobada para tu préstamo personal con Garantía de hasta $75,000.00!* 🎉\n\nQueremos acompañarte en este proceso para que accedas a todos los beneficios cuanto antes.\n\nPara acompañarte y resolver todas tus dudas, por favor selecciona una de las siguientes opciones 👇"
        },
        {
            "cleaned_phone_number": "1112223333",
            "creation_time": "2025-05-07 11:00:30.000000 UTC",
            "msg_from": "user",
            "message": "{\"button\":\"Me interesa\",\"entities\":\"{}\",\"intent\":\"some_intent_here\"}"
        },
        {
            "cleaned_phone_number": "1112223333",
            "creation_time": "2025-05-07 11:01:00.000000 UTC",
            "msg_from": "bot",
            "message": "¡Estás a un paso de la aprobación de tu préstamo personal! 🙌\nEsta oferta es por tiempo limitado, así que no esperes más.\nCompleta el proceso ahora, con tu información personal, y asegura tu préstamo en minutos 💸\n¡No pierdas la oportunidad! 🚀"
        }
        # No user response to handoff invitation
    ]
    
    sample_handoff_completed = [
        {
            "cleaned_phone_number": "4445556666",
            "creation_time": "2025-05-07 12:00:00.000000 UTC",
            "msg_from": "bot",
            "message": "Template:\n\n¡Hola *Ana Gomez*! 👋 Gracias por confiar en Kuna Capital.\n\n*¡Tienes una oferta preaprobada para tu préstamo personal con Garantía de hasta $60,000.00!* 🎉\n\nQueremos acompañarte en este proceso para que accedas a todos los beneficios cuanto antes.\n\nPara acompañarte y resolver todas tus dudas, por favor selecciona una de las siguientes opciones 👇"
        },
        {
            "cleaned_phone_number": "4445556666",
            "creation_time": "2025-05-07 12:00:30.000000 UTC",
            "msg_from": "user",
            "message": "{\"button\":\"Me interesa\",\"entities\":\"{}\",\"intent\":\"some_intent_here\"}"
        },
        {
            "cleaned_phone_number": "4445556666",
            "creation_time": "2025-05-07 12:01:00.000000 UTC",
            "msg_from": "bot",
            "message": "¡Estás a un paso de la aprobación de tu préstamo personal! 🙌\nEsta oferta es por tiempo limitado, así que no esperes más.\nCompleta el proceso ahora, con tu información personal, y asegura tu préstamo en minutos 💸\n¡No pierdas la oportunidad! 🚀"
        },
        {
            "cleaned_phone_number": "4445556666",
            "creation_time": "2025-05-07 12:01:30.000000 UTC",
            "msg_from": "user",
            "message": "{\"button\":\"Empezar\",\"entities\":\"{}\",\"intent\":\"start-handoff\"}"
        },
        {
            "cleaned_phone_number": "4445556666",
            "creation_time": "2025-05-07 12:02:00.000000 UTC",
            "msg_from": "bot",
            "message": "Por favor completa el formulario..."
        },
        {
            "cleaned_phone_number": "4445556666",
            "creation_time": "2025-05-07 12:05:00.000000 UTC",
            "msg_from": "user",
            "message": "Ya terminé"
        },
        {
            "cleaned_phone_number": "4445556666",
            "creation_time": "2025-05-07 12:06:00.000000 UTC",
            "msg_from": "bot",
            "message": "Felicidades, tu préstamo ha sido aprobado exitosamente. Recibirás los fondos en tu cuenta."
        }
    ]
    
    print(f"Handoff Started: {analyze_diana_conversation(sample_handoff_started)}")
    print(f"Handoff Declined: {analyze_diana_conversation(sample_handoff_declined)}")
    print(f"Handoff Ignored: {analyze_diana_conversation(sample_handoff_ignored)}")
    print(f"Handoff Completed: {analyze_diana_conversation(sample_handoff_completed)}")
    
    # Original test cases
    sample_conversation_interested = [
        {
            "cleaned_phone_number": "8442656544",
            "creation_time": "2025-05-06 19:31:01.151000 UTC",
            "msg_from": "bot",
            "operator_alias": None,
            "message": "Template:\n\n¡Hola *Juan salomé lópez limón*! 👋 Gracias por confiar en Kuna Capital.\n\n*¡Tienes una oferta preaprobada para tu préstamo personal con Garantía de hasta $85,212.93!* 🎉\n\nQueremos acompañarte en este proceso para que accedas a todos los beneficios cuanto antes.\n\nPara acompañarte y resolver todas tus dudas, por favor selecciona una de las siguientes opciones 👇"
        },
        {
            "cleaned_phone_number": "8442656544",
            "creation_time": "2025-05-06 19:31:29.868000 UTC",
            "msg_from": "user",
            "operator_alias": None,
            "message": "{\"button\":\"Me interesa\",\"entities\":\"{}\",\"intent\":\"RuleBuilder:kavakcapital-qok4a8go95@b.m-1739896840354\"}"
        }
    ]

    sample_conversation_not_interested = [
        {
            "cleaned_phone_number": "1234567890",
            "creation_time": "2025-05-07 10:00:00.000000 UTC",
            "msg_from": "bot",
            "message": "Template:\n\n¡Hola *Maria Rodriguez*! 👋 Gracias por confiar en Kuna Capital.\n\n*¡Tienes una oferta preaprobada para tu préstamo personal con Garantía de hasta $50,000.00!* 🎉\n\nQueremos acompañarte en este proceso para que accedas a todos los beneficios cuanto antes.\n\nPara acompañarte y resolver todas tus dudas, por favor selecciona una de las siguientes opciones 👇"
        },
        {
            "cleaned_phone_number": "1234567890",
            "creation_time": "2025-05-07 10:00:30.000000 UTC",
            "msg_from": "user",
            "message": "{\"button\":\"de momento no\",\"entities\":\"{}\",\"intent\":\"some_intent_here\"}"
        }
    ]

    sample_conversation_ignored_json_error = [
        {
            "cleaned_phone_number": "1112223333",
            "creation_time": "2025-05-07 11:00:00.000000 UTC",
            "msg_from": "bot",
            "message": "Template:\n\n¡Hola *Carlos Santana*! 👋 Gracias por confiar en Kuna Capital.\n\n*¡Tienes una oferta preaprobada para tu préstamo personal con Garantía de hasta $75,000.00!* 🎉\n\nQueremos acompañarte en este proceso para que accedas a todos los beneficios cuanto antes.\n\nPara acompañarte y resolver todas tus dudas, por favor selecciona una de las siguientes opciones 👇"
        },
        {
            "cleaned_phone_number": "1112223333",
            "creation_time": "2025-05-07 11:00:30.000000 UTC",
            "msg_from": "user",
            "message": "Not a valid JSON response"
        }
    ]
    
    sample_conversation_ignored_no_user_reply = [
        {
            "cleaned_phone_number": "4445556666",
            "creation_time": "2025-05-07 12:00:00.000000 UTC",
            "msg_from": "bot",
            "message": "Template:\n\n¡Hola *Ana Gomez*! 👋 Gracias por confiar en Kuna Capital.\n\n*¡Tienes una oferta preaprobada para tu préstamo personal con Garantía de hasta $60,000.00!* 🎉\n\nQueremos acompañarte en este proceso para que accedas a todos los beneficios cuanto antes.\n\nPara acompañarte y resolver todas tus dudas, por favor selecciona una de las siguientes opciones 👇"
        }
    ]

    sample_conversation_no_offer = [
        {
            "cleaned_phone_number": "7778889999",
            "creation_time": "2025-05-07 13:00:00.000000 UTC",
            "msg_from": "bot",
            "message": "Hola, ¿cómo estás?"
        },
        {
            "cleaned_phone_number": "7778889999",
            "creation_time": "2025-05-07 13:00:30.000000 UTC",
            "msg_from": "user",
            "message": "Bien, gracias."
        }
    ]
    
    sample_conversation_other_button = [
        {
            "cleaned_phone_number": "8442656545",
            "creation_time": "2025-05-06 19:31:01.151000 UTC",
            "msg_from": "bot",
            "operator_alias": None,
            "message": "Template:\n\n¡Hola *Pedro Pascal*! 👋 Gracias por confiar en Kuna Capital.\n\n*¡Tienes una oferta preaprobada para tu préstamo personal con Garantía de hasta $100,000.00!* 🎉\n\nQueremos acompañarte en este proceso para que accedas a todos los beneficios cuanto antes.\n\nPara acompañarte y resolver todas tus dudas, por favor selecciona una de las siguientes opciones 👇"
        },
        {
            "cleaned_phone_number": "8442656545",
            "creation_time": "2025-05-06 19:31:29.868000 UTC",
            "msg_from": "user",
            "operator_alias": None,
            "message": "{\"button\":\"Otra opcion\",\"entities\":\"{}\",\"intent\":\"some_other_intent\"}"
        }
    ]


    print(f"Interested: {analyze_diana_conversation(sample_conversation_interested)}")
    print(f"Not Interested: {analyze_diana_conversation(sample_conversation_not_interested)}")
    print(f"Ignored (JSON Error): {analyze_diana_conversation(sample_conversation_ignored_json_error)}")
    print(f"Ignored (No User Reply): {analyze_diana_conversation(sample_conversation_ignored_no_user_reply)}")
    print(f"No Offer: {analyze_diana_conversation(sample_conversation_no_offer)}")
    print(f"Other Button: {analyze_diana_conversation(sample_conversation_other_button)}") 