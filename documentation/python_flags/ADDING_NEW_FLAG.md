# Step-by-Step Guide: Adding a New Python Flag

This document provides a practical example of adding a new Python flag to the lead_recovery project.

## Example Scenario

Let's say we want to add a new flag called `skip_sentiment_analysis` that would control whether conversation sentiment analysis is performed.

## Steps to Add the Flag

### 1. Update `python_flags_manager.py`

First, we need to add the flag to the `get_python_flag_columns` function:

```python
def get_python_flag_columns(
    skip_temporal_flags: bool = False,
    skip_metadata_extraction: bool = False,
    skip_handoff_detection: bool = False,
    skip_human_transfer: bool = False,
    skip_recovery_template_detection: bool = False,
    skip_consecutive_templates_count: bool = False,
    skip_handoff_invitation: bool = False,
    skip_handoff_started: bool = False,
    skip_handoff_finalized: bool = False,
    skip_detailed_temporal: bool = False,
    skip_hours_minutes: bool = False,
    skip_reactivation_flags: bool = False,
    skip_timestamps: bool = False,
    skip_user_message_flag: bool = False,
    skip_pre_validacion_detection: bool = False,
    skip_conversation_state: bool = False,
    skip_sentiment_analysis: bool = False  # Add the new flag here
) -> List[str]:
    """Get the list of Python-calculated flag columns.
    
    Args:
        # ... existing args
        skip_sentiment_analysis: Whether to skip sentiment analysis of conversation messages
        
    Returns:
        List of column names for all enabled Python flags
    """
    py_flag_columns = []
    
    # ... existing code
    
    # Add conditionals for the new flag
    if not skip_sentiment_analysis:
        py_flag_columns.append("sentiment_score")
        py_flag_columns.append("sentiment_category")
    
    return py_flag_columns
```

Then, we need to add the flag to the `get_python_flags_from_meta` function:

```python
def get_python_flags_from_meta(meta_config: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    """Extract skip flag values from meta_config."""
    # Default values for all skip flags (don't skip by default)
    skip_flags = {
        "skip_temporal_flags": False,
        "skip_metadata_extraction": False,
        "skip_handoff_detection": False,
        "skip_human_transfer": False,
        "skip_recovery_template_detection": False,
        "skip_consecutive_templates_count": False,
        "skip_handoff_invitation": False,
        "skip_handoff_started": False,
        "skip_handoff_finalized": False,
        "skip_detailed_temporal": False,
        "skip_hours_minutes": False,
        "skip_reactivation_flags": False,
        "skip_timestamps": False,
        "skip_user_message_flag": False,
        "skip_pre_validacion_detection": False,
        "skip_conversation_state": False,
        "skip_sentiment_analysis": False  # Add the new flag here
    }
    
    # ... rest of function
```

### 2. Update the CLI interface in `run.py`

Add the flag to the `run_pipeline` function:

```python
@app.callback(invoke_without_command=True)
def run_pipeline(
    recipe: str = typer.Argument(..., help="Recipe name to run, must exist in recipes/ directory."),
    # ... existing parameters
    skip_sentiment_analysis: bool = typer.Option(False, help="Skip sentiment analysis of conversation messages"),
    # ... other parameters
):
    # ... existing code
    
    # Add to override_options dictionary
    override_options = {
        # ... existing options
        "skip_sentiment_analysis": skip_sentiment_analysis,
        # ... other options
    }
```

### 3. Update the CLI interface in `summarize.py`

Extract the flag from override_options and pass it to `run_summarization_step`:

```python
@app.callback(invoke_without_command=True)
def summarize(
    # ... existing parameters
):
    # ... existing code
    
    # Extract flag from meta_config
    skip_sentiment_analysis_from_meta = override_options.get("skip_sentiment_analysis", False)
    
    # ... existing code
    
    # Pass flag to run_summarization_step
    loop.run_until_complete(
        run_summarization_step(
            # ... existing parameters
            skip_sentiment_analysis=skip_sentiment_analysis_from_meta,
            # ... other parameters
        )
    )
```

### 4. Update `analysis.py`

Add the parameter to the `run_summarization_step` function and use it:

```python
async def run_summarization_step(
    output_dir: Path,
    # ... existing parameters
    skip_sentiment_analysis: bool = False,
    # ... other parameters
):
    """Run the conversation summarization step.
    
    Args:
        # ... existing args
        skip_sentiment_analysis: Skip sentiment analysis of conversation messages
        # ... other args
    """
    # ... existing code
    
    # Log the new flag
    logger.info(f"Using skip_sentiment_analysis = {skip_sentiment_analysis}")
    
    # ... existing code
    
    # Use the flag in get_python_flag_columns call
    python_flag_columns = get_python_flag_columns(
        # ... existing parameters
        skip_sentiment_analysis=skip_sentiment_analysis,
        # ... other parameters
    )
    
    # ... existing code
    
    # Implement the sentiment analysis functionality
    if not skip_sentiment_analysis:
        # Example: Add sentiment analysis to the processing logic
        for phone, group in phone_groups:
            # Perform sentiment analysis here
            # Store results in a dictionary that can be merged with other results
```

### 5. Implement the Functionality

Create a new module or function to implement the sentiment analysis:

```python
# lead_recovery/sentiment_analysis.py
from typing import Dict, Any, List
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def analyze_sentiment(conversation_df: pd.DataFrame, skip: bool = False) -> Dict[str, Any]:
    """Analyze sentiment in a conversation.
    
    Args:
        conversation_df: DataFrame containing conversation messages
        skip: Whether to skip sentiment analysis
        
    Returns:
        Dictionary containing sentiment results
    """
    if skip:
        return {"sentiment_score": 0.0, "sentiment_category": "NEUTRAL"}
    
    try:
        # Example implementation using a simple rule-based approach
        # In a real implementation, you might use a proper NLP library
        
        if conversation_df.empty or "message" not in conversation_df.columns:
            logger.warning("Cannot analyze sentiment: empty conversation or missing 'message' column")
            return {"sentiment_score": 0.0, "sentiment_category": "NEUTRAL"}
        
        # Concatenate all messages
        all_text = " ".join(conversation_df["message"].astype(str))
        
        # Simple keyword-based sentiment scoring
        positive_words = ["happy", "great", "excellent", "thanks", "good", "love"]
        negative_words = ["bad", "terrible", "awful", "angry", "hate", "problem"]
        
        positive_count = sum(1 for word in positive_words if word in all_text.lower())
        negative_count = sum(1 for word in negative_words if word in all_text.lower())
        
        # Calculate score between -1.0 and 1.0
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
        else:
            score = (positive_count - negative_count) / total
        
        # Determine category
        if score > 0.3:
            category = "POSITIVE"
        elif score < -0.3:
            category = "NEGATIVE"
        else:
            category = "NEUTRAL"
        
        return {
            "sentiment_score": round(score, 2),
            "sentiment_category": category
        }
    
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}", exc_info=True)
        return {"sentiment_score": 0.0, "sentiment_category": "ERROR"}
```

### 6. Use the New Functionality in `analysis.py`

Import and use the sentiment analysis function:

```python
from .sentiment_analysis import analyze_sentiment

# ... existing code

async def process_conversation(phone: str, conv_df: pd.DataFrame):
    # ... existing code
    
    # Add sentiment analysis
    if not skip_sentiment_analysis:
        sentiment_results = analyze_sentiment(conv_df, skip=skip_sentiment_analysis)
        # Add results to the overall results dictionary
        summaries[phone].update(sentiment_results)
```

### 7. Test the New Flag

Test both enabling and disabling the flag:

```bash
# Test with sentiment analysis enabled (default)
python -m lead_recovery.cli.main run --recipe your_recipe_name

# Test with sentiment analysis disabled
python -m lead_recovery.cli.main run --recipe your_recipe_name --skip-sentiment-analysis
```

### 8. Update Documentation

Update the project's README or other documentation to mention the new flag:

```markdown
## Common Command Options

* `--skip-sentiment-analysis`: Skip sentiment analysis of conversation messages
```

## Best Practices When Adding Flags

1. **Follow naming conventions**: Use `skip_` prefix for flags that disable functionality
2. **Default to enabled**: Set the default value for `skip_` flags to `False`
3. **Provide clear help text**: Make it clear what the flag does in the CLI help text
4. **Add logging**: Log when the flag is used to aid debugging
5. **Implement graceful fallbacks**: Ensure the code handles the flag being both true and false
6. **Update all necessary files**: Always update all the relevant files discussed above
7. **Add tests**: Create tests to verify the flag works correctly

## Common Pitfalls

1. **Forgetting components**: Ensure you update all components (python_flags_manager.py, CLI interfaces, analysis.py)
2. **Inconsistent naming**: Keep the flag name consistent across all files
3. **Missing documentation**: Always update documentation to include the new flag
4. **Not testing both states**: Test both when the flag is enabled and disabled
5. **Forgetting default values**: Ensure default values are consistent across all files 