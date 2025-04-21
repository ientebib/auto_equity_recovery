"""summarizer.py
Conversation summarisation using OpenAI ChatCompletion with retries.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List

import pandas as pd
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from pathlib import Path
import tiktoken

from .config import settings

logger = logging.getLogger(__name__)


class ConversationSummarizer:
    """Generate text summary for a single conversation DataFrame."""

    def __init__(self, model: str = "gpt-3.5-turbo", max_tokens: int = 512):
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model
        self.max_tokens = max_tokens
        
        # Load the custom prompt template
        prompt_path = Path(__file__).parent / "prompts" / "openai_prompt.txt"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
            logger.info("Loaded custom prompt template from %s", prompt_path)
        except Exception as e:
            logger.error("Failed to load prompt template: %s", str(e))
            self.prompt_template = "Summarize the following conversation:\n{conversation_text}"

    # ------------------------------------------------------------------ #
    @retry(wait=wait_exponential(multiplier=2, min=2, max=10), stop=stop_after_attempt(3))
    def _call_openai(self, messages: List[Dict[str, str]]) -> str:
        """Internal helper wrapped with exponential backoff retry."""
        # Use tiktoken for more accurate prompt token count
        try:
            encoding = tiktoken.encoding_for_model(self.model)
            num_tokens = sum(len(encoding.encode(msg["content"])) for msg in messages)
            logger.debug("Calling OpenAI API (model: %s) with %d tokens in prompt", self.model, num_tokens)
        except Exception: # Handle cases where encoding might fail (e.g., model not found)
             logger.warning("Could not get tiktoken encoding for model '%s'. Falling back to word count.", self.model)
             word_count = sum(len(msg["content"].split()) for msg in messages) 
             logger.debug("Calling OpenAI API (model: %s) with ~%d words in prompt", self.model, word_count)
        
        start_time = time.time()
        rsp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
        )
        duration = time.time() - start_time
        
        content = rsp.choices[0].message.content.strip()
        # Optionally, count response tokens too
        try:
            # Check if encoding was successfully obtained earlier
            if "encoding" in locals():
                response_tokens = len(encoding.encode(content))
                logger.debug(
                    "OpenAI API call completed in %.2f seconds. Response tokens: %d",
                    duration, response_tokens
                )
            else:
                # If encoding failed, log word count as fallback
                logger.debug(
                    "OpenAI API call completed in %.2f seconds. Response words: ~%d (tiktoken encoding failed earlier)",
                    duration, len(content.split())
                )
        except Exception as e: # Catch potential errors during encoding/logging, though less likely now
            logger.warning("Could not calculate response size: %s. Falling back to word count.", e)
            logger.debug(
                "OpenAI API call completed in %.2f seconds. Response words: ~%d",
                duration, len(content.split())
            )

        return content

    # ------------------------------------------------------------------ #
    def summarize(self, conv_df: pd.DataFrame) -> str:
        """Return a TL;DR summary for *conv_df*."""
        try:
            # Limit the conversation to avoid token limit issues
            # Taking first 5 and last 15 messages if more than 20 messages
            if len(conv_df) > 20:
                first_n = min(5, len(conv_df))
                last_n = min(15, len(conv_df) - first_n)
                truncated_df = pd.concat([
                    conv_df.head(first_n), 
                    conv_df.tail(last_n)
                ])
                logger.debug("Truncated conversation from %d to %d messages", 
                           len(conv_df), len(truncated_df))
                conv_df = truncated_df
            
            # Format the conversation
            conversation_text = "\n".join(
                f"{getattr(row, 'msg_from', 'Unknown Sender')}: {getattr(row, 'message', 'No Message')}" 
                for row in conv_df.itertuples(index=False)
            )
            
            # Apply the custom prompt template
            prompt = self.prompt_template.format(conversation_text=conversation_text)
            
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful customer‑support summarisation bot.",
                },
                {"role": "user", "content": prompt},
            ]
            summary = self._call_openai(messages)
            return summary
        except Exception:  # noqa: BLE001
            logger.exception("Failed to summarise conversation")
            raise 