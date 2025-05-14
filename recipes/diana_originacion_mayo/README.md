# Diana Originación Mayo Recipe

This recipe analyzes WhatsApp conversations for users who have received specific loan offer template messages and tracks how they responded.

## Purpose

Track which users:
1. Received a specific loan offer template message
2. Responded with "Me interesa" (Interested)
3. Responded with "de momento no" (Not interested)
4. Ignored the message or gave other responses

## Usage

### Prerequisites
- Python 3.8+
- Google Cloud credentials configured
- Input file `output_run/diana_originacion_mayo/leads.csv` containing phone numbers to analyze

### Running the Recipe

From the project root directory:

```
python -m recipes.diana_originacion_mayo
```

### Output

Results will be saved to:
- `output_run/diana_originacion_mayo/{timestamp}/diana_results.csv` - CSV file with analysis by phone number
- `output_run/diana_originacion_mayo/{timestamp}/summary.txt` - Summary of overall results

### Expected Output Format

The CSV file will contain:
- `cleaned_phone`: Phone number
- `offer_detected`: Whether the offer template was found (TRUE/FALSE)
- `user_response`: One of "Me interesa", "de momento no", "ignored", "No offer sent", or "No conversation found"

## Technical Details

The analyzer uses regular expressions to identify the specific offer template message and parses JSON responses to identify button clicks in the user's replies.

## Debugging

If you need to test the analyzer without running the full recipe, you can directly run:

```
python recipes/diana_originacion_mayo/analyzer.py
```

This will run the pre-defined test cases included in the analyzer module. 