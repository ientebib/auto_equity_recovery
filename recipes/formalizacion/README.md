# Formalizacion Recipe - Technical Documentation

## Overview

The Formalizacion recipe analyzes conversations from the credit formalization phase using Google Sheets as a data source and BigQuery for conversation retrieval. **This recipe includes a clean solution that eliminates unwanted columns and provides actionable insights.**

## 🎯 **RECOMMENDED: Clean Solution**

### Quick Command
```bash
python3 run_clean_formalizacion.py
```

**Benefits:**
- ✅ **12 clean columns** (eliminates 13+ unwanted columns)
- ✅ **Smart analysis summaries** with actionable insights
- ✅ **Auto-upload to Google Sheets** "Bot Live" worksheet
- ✅ **No framework limitations** - works around Lead Recovery constraints

### Clean Output Structure
```
Real Data (6 columns):
├── agente              # Agent name (@Mariana Mercado)
├── asset_id            # Asset ID (10058861)
├── nombre              # Client name (Julio Esparza Camacho)
├── correo              # Client email (hiroesparza@gmail.com)
├── cleaned_phone       # Phone number (9982598602)
└── lead_created_at     # Date (2025-06-05)

Analysis Results (6 columns):
├── resumen_general     # NEW! Crisp overall summary
├── documentos_enviados_analisis
├── enviado_a_validacion
├── calidad_atencion_agente
├── objecion_principal_cliente
└── gps_instalacion_agendada
```

## Technical Architecture

### Data Pipeline
1. **Google Sheets Input** → `fetch_leads_from_sheets.py`
2. **Phone Standardization** → Extract last 10 digits
3. **Date Filtering** → Last 30 days from "Fecha Instalación GPS"
4. **BigQuery Filtering** → Formalization conversations only
5. **LLM Analysis** → 6 structured questions (5 original + overall summary)
6. **Clean Processing** → `run_clean_formalizacion.py` (RECOMMENDED)
7. **Google Sheets Output** → "Bot Live" worksheet

### Key Components

#### Google Sheets Integration
- **Service Account**: `/Users/isaacentebi/Desktop/Kavak Capital Service Account.json`
- **Input Sheet**: `1nAU3lsPo98dTqaGOChhJM4WQKhyeItaqRGb5TvEFaXg`
- **Input Worksheet**: "Autoequity"
- **Output Worksheet**: "Bot Live"

#### Input Data Mapping
```
Column A: Fecha Instalación GPS → lead_created_at (date filtering)
Column B: Agente → agente (real agent names)
Column C: Asset ID → asset_id (real asset identifiers)
Column D: Nombre → nombre (real client names)
Column E: Correo → correo (real client emails)
Column F: Número de teléfono → cleaned_phone (standardized)
```

#### BigQuery Conversation Filtering
```sql
-- File: formalizacion_bigquery.sql
-- Filters for formalization phase conversations only
WHERE conversation_text REGEXP r'y estaré acompañándote en esta última parte del proceso'
```

#### LLM Analysis Configuration
```yaml
# File: meta.yml
expected_llm_keys:
  resumen_general:           # NEW! Overall crisp summary
  documentos_enviados_analisis:
  enviado_a_validacion:
  calidad_atencion_agente:
  objecion_principal_cliente:
  gps_instalacion_agendada:
```

## File Structure

```
recipes/formalizacion/
├── 📋 EXECUTION_GUIDE.md          # User-friendly guide
├── 📄 README.md                   # This technical documentation
├── 🎯 CLEAN_SOLUTION.md           # Clean solution details
├── ⚙️  meta.yml                    # Recipe configuration
├── 🤖 prompt.txt                  # LLM analysis prompt
├── 🔍 formalizacion_bigquery.sql  # Conversation filtering
├── 📊 fetch_leads_from_sheets.py  # Google Sheets data fetcher
├── 🚀 run_formalizacion.py        # Standard recipe runner
└── ✨ run_clean_formalizacion.py  # RECOMMENDED: Clean solution
```

## Implementation Details

### Phone Number Standardization
```python
def standardize_phone(phone_str):
    """Extract last 10 digits from phone number"""
    digits = re.sub(r'\D', '', str(phone_str))
    return digits[-10:] if len(digits) >= 10 else digits
```

### Date Filtering Logic
```python
# Filter for last 30 days from "Fecha Instalación GPS"
cutoff_date = datetime.now() - timedelta(days=30)
filtered_df = df[df['parsed_date'] >= cutoff_date]
```

### Smart Summary Generation
```python
def generate_smart_summary(row):
    """Generate crisp, actionable summaries based on analysis results"""
    validation = str(row.get('enviado_a_validacion', 'No claro')).lower()
    quality = str(row.get('calidad_atencion_agente', '')).lower()
    gps = str(row.get('gps_instalacion_agendada', '')).lower()
    
    if 'sí' in validation:
        if 'agendada' in gps:
            return "Proceso fluido: documentos validados y GPS agendado"
        else:
            return "Documentos en validación, GPS pendiente"
    # ... additional logic
```

## Alternative: Standard Recipe (Not Recommended)

### Standard Command
```bash
python3 run_formalizacion.py
```

**Issues with Standard Recipe:**
- ❌ **25+ columns** with unwanted data
- ❌ **Framework limitations** add built-in processors
- ❌ **Messy output** requires manual cleaning
- ❌ **No overall summary** field

### Standard Output Issues
```
Unwanted columns added by framework:
├── IS_WITHIN_REACTIVATION_WINDOW
├── IS_RECOVERY_PHASE_ELIGIBLE  
├── GPS (mixed up data)
├── Detalles (verbose, poorly formatted)
├── Ejemplos (unnecessary examples)
├── summary (generic summaries)
└── [8+ other metadata columns]
```

## Performance Metrics

### Clean Solution Performance
- **Input processing**: ~210 leads from Google Sheets
- **Conversation retrieval**: ~7,300+ messages from BigQuery
- **Analysis success**: ~44 leads with conversation data
- **Processing time**: ~2-3 minutes
- **Output quality**: 12 clean, actionable columns
- **Upload success**: 100% to Google Sheets

### Data Quality Improvements
- **Before**: 25 messy columns, verbose responses, formatting issues
- **After**: 12 clean columns, crisp summaries, ready-to-use data
- **Improvement**: 52% reduction in columns, 100% actionable data

## Error Handling

### Google Sheets Authentication
```python
credentials_path = "/Users/isaacentebi/Desktop/Kavak Capital Service Account.json"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(credentials_path, scopes=scope)
```

### NaN Value Cleaning
```python
# Clean all NaN values before upload
df = df.fillna('')
df = df.astype(str)
df = df.replace(['nan', 'None', 'NaN'], '')
```

### Conversation Data Validation
```python
# Handle leads without conversation data
if pd.isna(row.get('documentos_enviados_analisis')):
    return "Sin conversación registrada"
```

## Integration Notes

### Compatibility with Other Recipes
- **No impact**: Clean solution is self-contained
- **Framework intact**: Standard recipe still works
- **Isolated processing**: Post-processing approach doesn't affect core system
- **Safe deployment**: No changes to shared components

### Future Enhancements
- **Taxonomy expansion**: Add more structured analysis categories
- **Real-time processing**: Integrate with live data streams
- **Dashboard integration**: Connect to modern dashboard system
- **Alert system**: Notify on stuck clients or process issues

## Troubleshooting

### Common Issues
1. **Google Sheets upload fails**: Check credentials and permissions
2. **No conversation data**: Normal for leads without formalization conversations
3. **Module import errors**: Use clean solution to bypass framework issues
4. **Date parsing errors**: Verify "Fecha Instalación GPS" format

### Debug Commands
```bash
# Check clean output
head -5 ../../output_run/formalizacion/latest_clean.csv

# Verify data quality
python3 -c "import pandas as pd; df = pd.read_csv('../../output_run/formalizacion/latest_clean.csv'); print(f'Shape: {df.shape}'); print(f'Columns: {list(df.columns)}')"

# Test Google Sheets connection
python3 -c "from run_clean_formalizacion import upload_to_sheets; print('Testing upload...')"
```

---

**Recommended Approach**: Use `run_clean_formalizacion.py` for production  
**Output File**: `output_run/formalizacion/latest_clean.csv`  
**Google Sheets**: Auto-uploaded to "Bot Live" worksheet  
**Status**: ✅ Production ready with clean, actionable results 