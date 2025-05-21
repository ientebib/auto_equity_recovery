"""Tests for the ConversationSummarizer class."""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from lead_recovery.exceptions import ApiError, ValidationError
from lead_recovery.summarizer import ConversationSummarizer


@pytest.fixture
def sample_prompt_text():
    """Create a temporary sample prompt file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("Test prompt containing {conversation_text} and {HOY_ES} and {LAST_QUERY_TIMESTAMP} and {delta_min}")
        temp_path = f.name
    
    yield temp_path
    
    # Clean up
    os.unlink(temp_path)


def test_summarizer_init_checks_api_key():
    """Test that the summarizer checks for an API key."""
    with patch("lead_recovery.summarizer.settings.OPENAI_API_KEY", None):
        with pytest.raises(ApiError, match="OPENAI_API_KEY is not set"):
            ConversationSummarizer()


def test_summarizer_loads_prompt_file(sample_prompt_text):
    """Test that the summarizer loads a prompt template correctly."""
    with patch("lead_recovery.summarizer.settings.OPENAI_API_KEY", "fake-key"):
        summarizer = ConversationSummarizer(prompt_template_path=sample_prompt_text)
        assert "Test prompt containing" in summarizer.prompt_template
        assert "{conversation_text}" in summarizer.prompt_template


def test_summarizer_init_missing_prompt_file():
    """Test that the summarizer raises an error when the prompt file is missing."""
    with patch("lead_recovery.summarizer.settings.OPENAI_API_KEY", "fake-key"):
        with pytest.raises(FileNotFoundError, match="Could not find prompt template file"):
            ConversationSummarizer(prompt_template_path="/nonexistent/path/to/prompt.txt")


def test_tiktoken_estimation():
    """Test that the token estimator works correctly with tiktoken."""
    with patch("lead_recovery.summarizer.settings.OPENAI_API_KEY", "fake-key"):
        summarizer = ConversationSummarizer()
        
        # Mock the tiktoken encoding
        with patch.object(summarizer.encoding, 'encode', return_value=list(range(10))):
            messages = [{"role": "user", "content": "Hello world"}]
            tokens = summarizer.estimate_tokens(messages)
            
            # Should be the length of the encoded tokens (10) + overhead
            assert tokens == 10 + 4 + 3  # tokens + message overhead + format overhead


@pytest.mark.asyncio
async def test_call_openai_success():
    """Test the _call_openai method with a successful response."""
    with patch("lead_recovery.summarizer.settings.OPENAI_API_KEY", "fake-key"):
        summarizer = ConversationSummarizer()
        
        # Mock the AsyncOpenAI client responses.create method
        mock_response = MagicMock()
        mock_response.status = "completed"
        mock_response.output_text = "YAML response from API"
        mock_response.usage.input_tokens = 50
        mock_response.usage.output_tokens = 30
        mock_response.usage.output_tokens_details.reasoning_tokens = 10
        
        mock_client = AsyncMock()
        mock_client.responses.create.return_value = mock_response
        
        with patch.object(summarizer, '_async_client', mock_client):
            messages = [{"role": "system", "content": "You are a helpful assistant"}]
            result = await summarizer._call_openai(messages)
            
            # Assert the result is as expected
            assert result == "YAML response from API"
            
            # Assert the client was called with expected parameters
            mock_client.responses.create.assert_called_once()
            call_args = mock_client.responses.create.call_args[1]
            assert call_args["model"] == summarizer.model
            assert call_args["input"] == messages


@pytest.mark.asyncio
async def test_call_openai_error():
    """Test the _call_openai method with an API error."""
    with patch("lead_recovery.summarizer.settings.OPENAI_API_KEY", "fake-key"):
        summarizer = ConversationSummarizer()
        
        # Mock the AsyncOpenAI client to raise an error on both attempts
        mock_client = AsyncMock()
        api_exception = Exception("API Error")
        mock_client.responses.create.side_effect = api_exception
        mock_client.chat.completions.create.side_effect = api_exception # Mock fallback too
        
        with patch.object(summarizer, '_async_client', mock_client):
            messages = [{"role": "system", "content": "You are a helpful assistant"}]
            
            with pytest.raises(ApiError, match="Unexpected error in OpenAI call"):
                await summarizer._call_openai(messages)


@pytest.mark.asyncio
async def test_summarize_with_validation_failure():
    """Test that summarize correctly validates the YAML output."""
    with patch("lead_recovery.summarizer.settings.OPENAI_API_KEY", "fake-key"):
        # Set up expected keys for validation
        expected_keys = ["key1", "key2", "key3"]
        # Pass keys via meta_config
        mock_meta_config = {
            "llm_config": {
                "expected_llm_keys": {k: {} for k in expected_keys} # Create a dict structure similar to meta.yml
            }
        }
        summarizer = ConversationSummarizer(meta_config=mock_meta_config)
        
        # Create mock conversation DataFrame
        conv_df = pd.DataFrame({
            "creation_time": ["2025-01-01T12:00:00"],
            "msg_from": ["User"],
            "message": ["Hello"],
            "cleaned_phone_number": ["1234567890"]
        })
        
        # Mock the _call_openai method to return incomplete YAML
        with patch.object(summarizer, '_call_openai') as mock_call:
            mock_call.return_value = """
            key1: value1
            # Missing key2 and key3
            """
            
            # Patch the parse_yaml_dict function to return incomplete data
            with patch("lead_recovery.summarizer_helpers.parse_yaml_dict") as mock_parse:
                mock_parse.return_value = {"key1": "value1"}
                
                # Should raise ValidationError due to missing keys
                with pytest.raises(ValidationError, match="Missing keys"):
                    await summarizer.summarize(conv_df)


@pytest.mark.asyncio
async def test_summarize_success():
    """Test the complete summarize method with a successful run."""
    with patch("lead_recovery.summarizer.settings.OPENAI_API_KEY", "fake-key"):
        # Set up expected keys for validation
        expected_keys = ["key1", "key2", "key3"]
        # Pass keys via meta_config
        mock_meta_config = {
            "llm_config": {
                "expected_llm_keys": {k: {} for k in expected_keys} # Create a dict structure similar to meta.yml
            }
        }
        summarizer = ConversationSummarizer(meta_config=mock_meta_config)
        
        # Create mock conversation DataFrame
        conv_df = pd.DataFrame({
            "creation_time": ["2025-01-01T12:00:00"],
            "msg_from": ["User"],
            "message": ["Hello"],
            "cleaned_phone_number": ["1234567890"]
        })
        
        # Mock the _call_openai method to return valid YAML
        with patch.object(summarizer, '_call_openai') as mock_call:
            mock_call.return_value = """
            key1: value1
            key2: value2
            key3: value3
            """
            
            # Patch the parse_yaml_dict function to return complete data
            with patch("lead_recovery.summarizer_helpers.parse_yaml_dict") as mock_parse:
                mock_parse.return_value = {
                    "key1": "value1",
                    "key2": "value2",
                    "key3": "value3"
                }
                
                # Should complete successfully
                result = await summarizer.summarize(conv_df)
                
                # Check the result
                assert "key1" in result
                assert result["key1"] == "value1"
                assert "conversation_digest" in result  # Should add metadata row
