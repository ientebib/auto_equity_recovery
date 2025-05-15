from typing import Any, Dict, List, Optional

import pandas as pd


def strip_accents(text: str) -> str:
    """
    Remove accents from Spanish text to simplify pattern matching.
    
    Args:
        text: Text string to process
        
    Returns:
        Text with accents removed
    """
    accent_map = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ü': 'u', 'Ü': 'U', 'ñ': 'n', 'Ñ': 'N'
    }
    for accented, plain in accent_map.items():
        text = text.replace(accented, plain)
    return text

def convert_df_to_message_list(conversation_df: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    """
    Convert a DataFrame of conversation data to a list of message dictionaries.
    
    This helps maintain compatibility with legacy code that expects message data
    in list format.
    
    Args:
        conversation_df: DataFrame containing conversation messages
        
    Returns:
        List of message dictionaries
    """
    if conversation_df is None or conversation_df.empty:
        return []
    
    message_list = []
    
    for _, row in conversation_df.iterrows():
        message = {}
        for col in row.index:
            message[col] = row[col]
        message_list.append(message)
    
    return message_list 