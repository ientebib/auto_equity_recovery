"""
Utility functions for clipboard operations in Streamlit
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

def copy_to_clipboard_js(text: str, button_text: str = "📋 Copy", success_text: str = "Copied!") -> bool:
    """
    Create a button that copies text to clipboard using JavaScript.
    Returns True if button was clicked.
    """
    
    # Handle NaN and non-string values
    if pd.isna(text) or text is None:
        text = ""
    else:
        text = str(text)
    
    # Skip if text is empty or just whitespace
    if not text.strip():
        st.info("No message to copy")
        return False
    
    # Create a unique key for this component
    import hashlib
    key = hashlib.md5(text.encode()).hexdigest()[:8]
    
    # Escape text for JavaScript (handle quotes and newlines)
    escaped_text = text.replace('\\', '\\\\').replace('`', '\\`').replace('\n', '\\n').replace('\r', '\\r').replace("'", "\\'").replace('"', '\\"')
    
    # JavaScript code for copying to clipboard
    copy_js = f"""
    <div>
        <button onclick="copyToClipboard{key}()" 
                style="background: #1f77b4; color: white; border: none; padding: 8px 16px; 
                       border-radius: 4px; cursor: pointer; font-size: 14px;"
                onmouseover="this.style.opacity='0.8'" 
                onmouseout="this.style.opacity='1'">
            {button_text}
        </button>
        <span id="status{key}" style="margin-left: 10px; color: green; font-weight: bold;"></span>
    </div>
    
    <script>
    function copyToClipboard{key}() {{
        const text = `{escaped_text}`;
        
        if (navigator.clipboard && navigator.clipboard.writeText) {{
            navigator.clipboard.writeText(text).then(function() {{
                document.getElementById('status{key}').innerText = '{success_text}';
                setTimeout(function() {{
                    document.getElementById('status{key}').innerText = '';
                }}, 2000);
            }}, function(err) {{
                console.error('Could not copy text: ', err);
                fallbackCopy{key}(text);
            }});
        }} else {{
            fallbackCopy{key}(text);
        }}
    }}
    
    function fallbackCopy{key}(text) {{
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        textArea.style.top = "-999999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {{
            document.execCommand('copy');
            document.getElementById('status{key}').innerText = '{success_text}';
            setTimeout(function() {{
                document.getElementById('status{key}').innerText = '';
            }}, 2000);
        }} catch (err) {{
            console.error('Fallback: Oops, unable to copy', err);
            document.getElementById('status{key}').innerText = 'Copy failed';
        }}
        
        document.body.removeChild(textArea);
    }}
    </script>
    """
    
    components.html(copy_js, height=50)
    return False

def display_copyable_text(text: str, label: str = "Message", max_height: int = 100):
    """
    Display text in a styled container with copy functionality
    """
    
    # Handle NaN and non-string values
    if pd.isna(text) or text is None:
        text = ""
    else:
        text = str(text)
    
    # Create container with copy button
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.markdown(f"**{label}:**")
        if text.strip():
            # Display text in a styled info box
            st.info(text)
        else:
            st.info("No message available")
    
    with col2:
        if text.strip():
            copy_to_clipboard_js(text)
        else:
            st.markdown("*No message*")

def create_shareable_link(lead_data: dict) -> str:
    """
    Create a shareable link or summary for a lead
    """
    # Helper function to safely get string values
    def safe_get(key, default="N/A"):
        value = lead_data.get(key, default)
        if pd.isna(value) or value is None:
            return default
        return str(value)
    
    name = f"{safe_get('name')} {safe_get('last_name')}".strip()
    
    summary = f"""
Lead: {name}
Email: {safe_get('clean_email')}
Phone: {safe_get('cleaned_phone')}
Action: {safe_get('next_action_code')}
Reason: {safe_get('primary_stall_reason_code')}
Summary: {safe_get('summary', 'No summary')}
Suggested Message: {safe_get('suggested_message_es', 'No message')}
"""
    return summary.strip() 