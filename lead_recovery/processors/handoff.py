import re
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from lead_recovery.processors.utils import convert_df_to_message_list, strip_accents

from .base import BaseProcessor
from ._registry import register_processor

logger = logging.getLogger(__name__)

@register_processor
class HandoffProcessor(BaseProcessor):
    """
    Processor for analyzing handoff processes in conversations.
    
    Detects and tracks the flow of handoff invitations, user responses,
    and completion status for lead handoffs.
    """
    
    GENERATED_COLUMNS = [
        "handoff_invitation_detected",
        "handoff_response",
        "handoff_finalized"
    ]
    
    def _validate_params(self):
        """Validate processor-specific parameters."""
        known_params = {"skip_handoff_invitation", "skip_handoff_started", "skip_handoff_finalized"}
        for param in self.params:
            if param not in known_params:
                raise ValueError(f"Unknown parameter '{param}' for {self.__class__.__name__}")
    
    def process(self, 
                lead_data: pd.Series, 
                conversation_data: Optional[pd.DataFrame],
                existing_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze handoff process in conversation data.
        
        Args:
            lead_data: Series containing lead information
            conversation_data: DataFrame with conversation messages
            existing_results: Dictionary of results from previous processors
            
        Returns:
            Dictionary containing handoff analysis results
        """
        # Initialize default result
        result = {
            "handoff_invitation_detected": False,
            "handoff_response": "NO_INVITATION",
            "handoff_finalized": False
        }
        
        # Get skip parameters with defaults
        skip_handoff_invitation = self.params.get("skip_handoff_invitation", False)
        skip_handoff_started = self.params.get("skip_handoff_started", False)
        skip_handoff_finalized = self.params.get("skip_handoff_finalized", False)
        
        # Skip all checks if requested
        if skip_handoff_invitation and skip_handoff_started and skip_handoff_finalized:
            return result
            
        # Return early if no conversation data
        if conversation_data is None or conversation_data.empty:
            return result
            
        # Convert DataFrame to message list for compatibility
        conversation_messages = convert_df_to_message_list(conversation_data)
        if not conversation_messages:
            return result
        
        # First check if handoff invitation was sent (unless skipped)
        invitation_index = -1
        if not skip_handoff_invitation:
            for i, msg in enumerate(conversation_messages):
                if msg.get('msg_from') == 'bot':
                    if self._detect_handoff_invitation([msg], -1):
                        result["handoff_invitation_detected"] = True
                        invitation_index = i
                        break
        
        # If invitation was detected, check user response (unless skipped)
        if result["handoff_invitation_detected"] and not skip_handoff_started:
            result["handoff_response"] = self._detect_handoff_started(conversation_messages, invitation_index)
            
            # If user started handoff, check if it was finalized (unless skipped)
            if result["handoff_response"] == "STARTED_HANDOFF" and not skip_handoff_finalized:
                result["handoff_finalized"] = self._detect_handoff_finalized(conversation_messages, invitation_index)
        # NEW LOGIC: If invitation detected but response check is skipped, set a neutral/accurate response
        elif result["handoff_invitation_detected"] and skip_handoff_started:
            result["handoff_response"] = "INVITATION_SENT"

        logger.debug(
            f"HandoffProcessor results: Invitation detected: {result['handoff_invitation_detected']}, "
            f"Response: {result['handoff_response']}, Finalized: {result['handoff_finalized']}"
        )
        return result
    
    def _detect_handoff_invitation(self, conversation_messages: List[Dict[str, Any]], 
                              offer_message_index: int = -1) -> bool:
        """
        Detect if a handoff invitation was sent to the user.
        
        Args:
            conversation_messages: List of conversation message dictionaries
            offer_message_index: Index of the offer message, if known (to only check after this)
            
        Returns:
            True if handoff invitation was detected, False otherwise
        """
        # CRITICAL: These phrases/patterns are key to detection accuracy. Review and update periodically based on bot script changes and observed user interactions.
        # Regex to detect handoff invitation
        handoff_invitation_pattern = re.compile(
            r"Estas a un paso de la aprobacion de tu prestamo personal|"
            r"un paso de la aprobacion|"
            r"Esta oferta es por tiempo limitado|"
            r"Completa el proceso ahora|"
            r"asegura tu prestamo en minutos|"
            r"No pierdas la oportunidad", 
            re.IGNORECASE
        )
        
        for i, msg in enumerate(conversation_messages):
            # Only check bot messages
            if msg.get('msg_from') == 'bot' and (offer_message_index == -1 or i > offer_message_index):
                message_content = msg.get('message', '')
                
                # Check for handoff invitation
                if handoff_invitation_pattern.search(strip_accents(message_content)):
                    logger.debug("Handoff invitation phrase found.")
                    return True
        
        logger.debug("No handoff invitation phrases found in bot messages.")
        return False
    
    def _detect_handoff_started(self, conversation_messages: List[Dict[str, Any]], 
                          handoff_invitation_index: int) -> str:
        """
        Detect how the user responded to a handoff invitation.
        
        Args:
            conversation_messages: List of conversation message dictionaries
            handoff_invitation_index: Index of the handoff invitation message
            
        Returns:
            String indicating the user's response:
            - "NO_RESPONSE": No user messages after handoff invitation
            - "DECLINED_HANDOFF": User declined the handoff
            - "STARTED_HANDOFF": User initiated the handoff process
            - "UNCLEAR_RESPONSE": User responded, but intent is unclear
        """
        # Return NO_RESPONSE if no messages after invitation
        if handoff_invitation_index == -1 or handoff_invitation_index >= len(conversation_messages) - 1:
            logger.debug("No messages found after handoff invitation index or invalid index.")
            return "NO_RESPONSE"
        
        # Get user messages after invitation
        user_responses = [
            msg for i, msg in enumerate(conversation_messages) 
            if i > handoff_invitation_index and msg.get('msg_from') == 'user'
        ]
        
        # No user response yet
        if not user_responses:
            logger.debug("No user responses found after handoff invitation.")
            return "NO_RESPONSE"
            
        # Analyze first user response
        first_response = user_responses[0]
        response_text = strip_accents(first_response.get('message', '').lower())
        
        # CRITICAL: These phrases/patterns are key to detection accuracy. Review and update periodically based on bot script changes and observed user interactions.
        # Patterns for accepting handoff
        acceptance_patterns = [
            r"si(,)?\s+(quisiera|quiero)",
            r"acepto.*oferta",
            r"(quisiera|quiero|gustaria).*mas\s+informacion",
            r"me\s+interesa",
            r"(quisiera|quiero|gustaria).*saber\s+mas",
            r"continuar.*proceso",
            r"^si$",
            r"^si\s+por\s+favor$"
        ]
        
        # CRITICAL: These phrases/patterns are key to detection accuracy. Review and update periodically based on bot script changes and observed user interactions.
        # Patterns for declining handoff
        decline_patterns = [
            r"no(,)?\s+(quiero|quisiera|me\s+interesa)",
            r"no\s+gracias",
            r"rechaz[oa]",
            r"^no$"
        ]
        
        # Check for acceptance patterns
        for pattern in acceptance_patterns:
            if re.search(pattern, response_text):
                logger.debug(f"Handoff acceptance pattern matched: {pattern}")
                return "STARTED_HANDOFF"
                
        # Check for decline patterns
        for pattern in decline_patterns:
            if re.search(pattern, response_text):
                logger.debug(f"Handoff decline pattern matched: {pattern}")
                return "DECLINED_HANDOFF"
                
        # If neither clearly accepted nor declined, consider it unclear
        logger.debug("User response to handoff invitation is unclear.")
        return "UNCLEAR_RESPONSE"
    
    def _detect_handoff_finalized(self, conversation_messages: List[Dict[str, Any]], 
                            start_index: int = 0) -> bool:
        """
        Detect if a handoff process was completed.
        
        Args:
            conversation_messages: List of conversation message dictionaries
            start_index: Index to start searching from
            
        Returns:
            True if handoff was finalized, False otherwise
        """
        # CRITICAL: These phrases/patterns are key to detection accuracy. Review and update periodically based on bot script changes and observed user interactions.
        # Patterns indicating handoff completion
        completion_phrases = [
            r"tu\s+solicitud\s+ha\s+sido\s+enviada",
            r"tu\s+solicitud\s+ha\s+sido\s+recibida",
            r"tu\s+solicitud\s+ha\s+sido\s+procesada",
            r"gracias\s+por\s+completar\s+el\s+proceso",
            r"hemos\s+recibido\s+tu\s+solicitud"
        ]
        
        # Search for completion phrases in bot messages after start_index
        for i, msg in enumerate(conversation_messages):
            if i <= start_index or msg.get('msg_from') != 'bot':
                continue
                
            message_content = strip_accents(msg.get('message', '').lower())
            
            for pattern in completion_phrases:
                if re.search(pattern, message_content):
                    logger.debug(f"Handoff finalization phrase found: {pattern}")
                    return True
        
        logger.debug("No handoff finalization phrases found in bot messages after start index.")
        return False 