import json
import re
import unicodedata
import logging
from lead_recovery.handoff_detection import handoff_invitation, handoff_started, handoff_finalized

logger = logging.getLogger(__name__)

def strip_accents(text: str) -> str:
    if not isinstance(text, str):
        return ""
    try:
        nfd_form = unicodedata.normalize('NFD', text)
        return "".join(c for c in nfd_form if unicodedata.category(c) != 'Mn')
    except TypeError:
        return ""

def get_marzo_live_python_flags(conversation_messages: list) -> dict:
    """
    Analyzes conversation messages to extract handoff_reached and handoff_response flags.
    This logic is adapted from diana_originacion_mayo/analyzer.py.
    It first checks for an initial 'Me interesa' response to a generic offer,
    then uses the global handoff_detection functions to analyze the conversation.
    """
    
    # Initialize flags
    handoff_reached_flag = False
    handoff_response_flag = "NOT_APPLICABLE"
    handoff_finalized_flag = False
    
    # --- Part 1: Check for initial "Me interesa" ---
    # This part is simplified as we assume an offer was made and we are looking for interest
    # to then check for handoff. We need an offer_message_index as a reference point.
    
    offer_message_index = -1
    user_response_to_offer = None

    # Simplified offer detection pattern from diana_originacion_mayo
    # We need to find *an* offer to know when to look for "Me interesa"
    # This regex is illustrative; the actual offer might vary in marzo_cohorts_live.
    # For robustness, this might need to be more generic or rely on a different signal
    # if the initial offer message structure is unknown or highly variable.
    # For now, using a fairly generic part of the diana_originacion_mayo offer.
    offer_template_pattern = re.compile(
        r"Tienes una oferta preaprobada para tu prestamo personal", re.IGNORECASE
    )

    for i, msg in enumerate(conversation_messages):
        if msg.get('msg_from') == 'bot':
            message_content = msg.get('message', '')
            stripped_message_content = strip_accents(message_content)
            if offer_template_pattern.search(stripped_message_content):
                offer_message_index = i
                # Check for subsequent "Me interesa"
                if i + 1 < len(conversation_messages):
                    next_msg = conversation_messages[i+1]
                    if next_msg.get('msg_from') == 'user':
                        try:
                            raw_user_msg = next_msg.get('message', '{}')
                            user_msg_data = json.loads(raw_user_msg)
                            button_clicked = user_msg_data.get('button')
                            if button_clicked == "Me interesa":
                                user_response_to_offer = "Me interesa"
                                # Update offer_message_index to be the "Me interesa" response index
                                # so handoff search starts after this.
                                offer_message_index = i + 1 
                                break 
                        except (json.JSONDecodeError, AttributeError):
                            pass
    
    # Only proceed if "Me interesa" was found
    if user_response_to_offer == "Me interesa":
        phone_for_log = conversation_messages[0].get('cleaned_phone_number', 'unknown') # For logging
        
        # --- Part 2: Detect Handoff Invitation using global function
        handoff_reached_flag = handoff_invitation(conversation_messages, offer_message_index)
        
        # If handoff invitation was detected, find its index for further analysis
        handoff_invitation_index = -1
        if handoff_reached_flag:
            for i, msg in enumerate(conversation_messages):
                if msg.get('msg_from') == 'bot' and i > offer_message_index:
                    # Use the global function on a single message to find which one has the invitation
                    if handoff_invitation([msg], -1):
                        handoff_invitation_index = i
                        logger.info(f"[MarzoLiveAnalyzer] Handoff invitation found (msg {i}) for phone {phone_for_log}")
                        break
        
        if not handoff_reached_flag:
            logger.info(f"[MarzoLiveAnalyzer] No handoff invitation found for phone {phone_for_log} after 'Me interesa'")

        # --- Part 3: Detect Handoff Response (after handoff invitation) using global function
        if handoff_reached_flag and handoff_invitation_index >= 0:
            handoff_response_flag = handoff_started(conversation_messages, handoff_invitation_index)
            logger.info(f"[MarzoLiveAnalyzer] Handoff response for phone {phone_for_log}: {handoff_response_flag}")
            
            # --- Part 4: Detect Handoff Finalization if user started handoff
            if handoff_response_flag == "STARTED_HANDOFF":
                handoff_finalized_flag = handoff_finalized(conversation_messages, handoff_invitation_index)
                if handoff_finalized_flag:
                    logger.info(f"[MarzoLiveAnalyzer] Handoff finalized for phone {phone_for_log}")
    
    return {
        "handoff_reached": handoff_reached_flag,
        "handoff_response": handoff_response_flag,
        "handoff_finalized": handoff_finalized_flag
    }

if __name__ == '__main__':
    # Minimal test cases
    sample_conv_handoff_reached_started = [
        {"cleaned_phone_number": "test001", "msg_from": "bot", "message": "Tienes una oferta preaprobada para tu prestamo personal con Garantia..."},
        {"cleaned_phone_number": "test001", "msg_from": "user", "message": '{"button":"Me interesa"}'},
        {"cleaned_phone_number": "test001", "msg_from": "bot", "message": "Excelente! Estas a un paso de la aprobacion... Completa el proceso ahora."},
        {"cleaned_phone_number": "test001", "msg_from": "user", "message": '{"button":"Empezar"}'}
    ]
    print(f"Test Handoff Reached & Started: {get_marzo_live_python_flags(sample_conv_handoff_reached_started)}")

    sample_conv_handoff_reached_declined = [
        {"cleaned_phone_number": "test002", "msg_from": "bot", "message": "Tienes una oferta preaprobada para tu prestamo personal..."},
        {"cleaned_phone_number": "test002", "msg_from": "user", "message": '{"button":"Me interesa"}'},
        {"cleaned_phone_number": "test002", "msg_from": "bot", "message": "Que bueno! No pierdas la oportunidad y completa el proceso."},
        {"cleaned_phone_number": "test002", "msg_from": "user", "message": '{"button":"De momento no"}'}
    ]
    print(f"Test Handoff Reached & Declined: {get_marzo_live_python_flags(sample_conv_handoff_reached_declined)}")

    sample_conv_handoff_reached_ignored = [
        {"cleaned_phone_number": "test003", "msg_from": "bot", "message": "Oferta preaprobada para tu prestamo personal."},
        {"cleaned_phone_number": "test003", "msg_from": "user", "message": '{"button":"Me interesa"}'},
        {"cleaned_phone_number": "test003", "msg_from": "bot", "message": "Estas a un paso de la aprobacion..."}
        # No user response
    ]
    print(f"Test Handoff Reached & Ignored: {get_marzo_live_python_flags(sample_conv_handoff_reached_ignored)}")

    sample_conv_no_me_interesa = [
        {"cleaned_phone_number": "test004", "msg_from": "bot", "message": "Oferta preaprobada."},
        {"cleaned_phone_number": "test004", "msg_from": "user", "message": '{"button":"De momento no"}'}
    ]
    print(f"Test No 'Me interesa': {get_marzo_live_python_flags(sample_conv_no_me_interesa)}")
    
    sample_conv_no_handoff_invite = [
        {"cleaned_phone_number": "test005", "msg_from": "bot", "message": "Oferta preaprobada."},
        {"cleaned_phone_number": "test005", "msg_from": "user", "message": '{"button":"Me interesa"}'},
        {"cleaned_phone_number": "test005", "msg_from": "bot", "message": "Gracias por tu interes! Alguien te contactara."}
    ]
    print(f"Test No Handoff Invite: {get_marzo_live_python_flags(sample_conv_no_handoff_invite)}") 