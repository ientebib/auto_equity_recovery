import re
from typing import Dict, Any, List, Optional
import pandas as pd

from .base import BaseProcessor
from lead_recovery.processors.utils import strip_accents, convert_df_to_message_list

class TemplateDetectionProcessor(BaseProcessor):
    """
    Processor for detecting templated messages in conversations.
    
    Identifies various types of template messages including recovery templates,
    top-up templates, and counts consecutive template uses.
    """
    
    GENERATED_COLUMNS = [
        "recovery_template_detected",
        "topup_template_detected",
        "consecutive_recovery_templates_count"
    ]
    
    def _validate_params(self):
        """Validate processor-specific parameters."""
        known_params = {"template_type", "skip_recovery_template", "skip_topup_template", "skip_consecutive_count"}
        for param in self.params:
            if param not in known_params:
                raise ValueError(f"Unknown parameter '{param}' for {self.__class__.__name__}")
    
    def process(self, 
                lead_data: pd.Series, 
                conversation_data: Optional[pd.DataFrame],
                existing_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect template messages in conversation data.
        
        Args:
            lead_data: Series containing lead information
            conversation_data: DataFrame with conversation messages
            existing_results: Dictionary of results from previous processors
            
        Returns:
            Dictionary containing template detection results
        """
        # Initialize default result
        result = {
            "recovery_template_detected": False,
            "topup_template_detected": False,
            "consecutive_recovery_templates_count": 0
        }
        
        # Get skip parameters with defaults
        skip_recovery_template = self.params.get("skip_recovery_template", False)
        skip_topup_template = self.params.get("skip_topup_template", False)
        skip_consecutive_count = self.params.get("skip_consecutive_count", False)
        
        # Return early if no conversation data
        if conversation_data is None or conversation_data.empty:
            return result
            
        # Convert DataFrame to message list for compatibility
        conversation_messages = convert_df_to_message_list(conversation_data)
        if not conversation_messages:
            return result
        
        # Detect template types based on parameters
        template_type = self.params.get("template_type", "all").lower()
        
        # Check for recovery templates if not skipped
        if not skip_recovery_template and template_type in ["all", "recovery"]:
            # Check the last bot message for recovery template
            for msg in reversed(conversation_messages):
                if msg.get('msg_from') == 'bot':
                    message_text = msg.get('message', '')
                    result["recovery_template_detected"] = self._detect_recovery_template(message_text)
                    break
            
            # Count consecutive recovery templates if not skipped
            if not skip_consecutive_count:
                result["consecutive_recovery_templates_count"] = self._count_consecutive_recovery_templates(conversation_messages)
        
        # Check for top-up templates if not skipped
        if not skip_topup_template and template_type in ["all", "topup"]:
            # Check all bot messages for top-up template
            for msg in conversation_messages:
                if msg.get('msg_from') == 'bot':
                    message_text = msg.get('message', '')
                    if self._detect_topup_template(message_text):
                        result["topup_template_detected"] = True
                        break
        
        return result
    
    def _detect_recovery_template(self, message_text: str) -> bool:
        """
        Detect if a message is a recovery template.
        
        Args:
            message_text: The text of the message to check
            
        Returns:
            True if the message is a recovery template, False otherwise
        """
        # Recovery template key phrases
        recovery_phrases = [
            "préstamo por tu auto",
            "oferta pre aprobada",
            "aprovecha tu oferta",
            "espera de que nos proporciones tus documentos",
            "template:"
        ]
        
        # Check for any of the recovery phrases
        message_text_lower = message_text.lower()
        for phrase in recovery_phrases:
            if phrase in message_text_lower:
                return True
        
        return False
    
    def _detect_topup_template(self, message_text: str) -> bool:
        """
        Detect if a message is a top-up template.
        
        Args:
            message_text: The text of the message to check
            
        Returns:
            True if the message is a top-up template, False otherwise
        """
        # Top-up template regex patterns
        topup_patterns = [
            # Pattern for template message about pre-approved loan
            r"(?i)template:.*pre\s*aprobado",
            # Pattern for Hola + name + wave + pre-approved/credit message
            r"(?i)¡?hola\s+[\w\s]+!?\s+:?wave:?.*crédito\s+pre\s*aprobado",
            # Pattern for recognition of good payment behavior
            r"(?i).*reconocer\s+tu\s+excelente\s+comportamiento\s+de\s+pago",
            # Pattern for thanking for good client history
            r"(?i).*agradecerte\s+por\s+mantener\s+un\s+buen\s+historial\s+como\s+cliente"
        ]
        
        # Check for any of the top-up patterns
        for pattern in topup_patterns:
            if re.search(pattern, message_text):
                return True
        
        return False
    
    def _count_consecutive_recovery_templates(self, conversation_messages: List[Dict[str, Any]]) -> int:
        """
        Count consecutive recovery templates at the end of a conversation.
        
        Args:
            conversation_messages: List of conversation message dictionaries
            
        Returns:
            Number of consecutive recovery templates
        """
        count = 0
        # Start from the end and go backwards
        for i in range(len(conversation_messages) - 1, -1, -1):
            msg = conversation_messages[i]
            if msg.get('msg_from') == 'bot':
                message_text = msg.get('message', '')
                if self._detect_recovery_template(message_text):
                    count += 1
                else:
                    # Break the count if a non-recovery template is found
                    break
            else:
                # Break the count if a user message is found
                break
        
        return count 