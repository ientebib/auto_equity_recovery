# 📋 Formalizacion Recipe - Execution Guide

## 🎯 Overview

The **Formalizacion Recipe** analyzes conversations from clients who have reached the formalization phase of the credit process. It provides clean, actionable insights about document submission, validation status, agent service quality, and client progress.

## 🚀 **RECOMMENDED: Use the Clean Solution**

### Quick Start (Recommended)
```bash
cd recipes/formalizacion
python3 run_clean_formalizacion.py
```

**This gives you:**
- ✅ **12 clean columns** (no unwanted data)
- ✅ **Smart analysis summaries** 
- ✅ **Auto-upload to Google Sheets**
- ✅ **Ready-to-use results**

### Output Files
- `output_run/formalizacion/latest_clean.csv` ← **Use this file!**
- Auto-uploaded to "Bot Live" worksheet in Google Sheets

## 📁 Recipe Structure

```
recipes/formalizacion/
├── 📋 EXECUTION_GUIDE.md          # This guide
├── 📄 README.md                   # Technical documentation  
├── 🎯 CLEAN_SOLUTION.md           # Clean solution details
├── ⚙️  meta.yml                    # Recipe configuration
├── 🤖 prompt.txt                  # LLM analysis questions
├── 🔍 formalizacion_bigquery.sql  # Conversation filtering
├── 📊 fetch_leads_from_sheets.py  # Google Sheets integration
├── 🚀 run_formalizacion.py        # Standard recipe runner
└── ✨ run_clean_formalizacion.py  # RECOMMENDED: Clean solution
```

## 📊 Clean Output Structure

### Essential Data (12 columns):

**Real Client Data:**
- `agente` - Agent name (@Mariana Mercado)
- `asset_id` - Asset ID (10058861)
- `nombre` - Client name (Julio Esparza Camacho)
- `correo` - Client email (hiroesparza@gmail.com)
- `cleaned_phone` - Phone number (9982598602)
- `lead_created_at` - Date (2025-06-05)

**Analysis Results (STANDARDIZED TAXONOMIES):**
- `resumen_general` - **NEW!** Crisp overall summary
- `documentos_enviados_analisis` - **ONLY missing documents** ("Documentos completos" or "Faltan: [specific list]")
- `enviado_a_validacion` - **Simple taxonomy** ("Sí" or "No" only)
- `calidad_atencion_agente` - **Standardized quality** ("Excelente", "Buena", "Regular", "Mala")
- `objecion_principal_cliente` - **Standard categories** ("Sin objeciones", "Logística GPS", "Documentos faltantes", etc.)
- `gps_instalacion_agendada` - **Simple GPS status** ("GPS agendado", "GPS completado", "GPS no agendado", "GPS pendiente")

## 🧠 Smart Analysis Examples

The `resumen_general` field provides actionable insights:

- **"Sin conversación registrada"** - No conversation data found
- **"Proceso fluido: documentos validados y GPS agendado"** - Everything on track
- **"Documentos en validación, GPS pendiente"** - Waiting for validation
- **"Cliente atascado: documentos sin validar, atención deficiente"** - Needs attention
- **"Cliente necesita enviar documentos faltantes"** - Action required

## 🔄 Daily Workflow

### 1. Run Analysis
```bash
cd recipes/formalizacion
python3 run_clean_formalizacion.py
```

### 2. Check Results
- **Local file:** `output_run/formalizacion/latest_clean.csv`
- **Google Sheets:** "Bot Live" worksheet (auto-uploaded)

### 3. Take Action
- Review `resumen_general` for quick insights
- Focus on leads with conversation data (44 out of 210)
- Identify stuck clients and process issues

## ⚙️ Alternative: Standard Recipe (Not Recommended)

If you need to run the standard recipe (with messy output):

```bash
cd recipes/formalizacion
python3 run_formalizacion.py
```

**Note:** This creates messy output with 25+ columns. Use the clean solution instead.

## 🔧 Configuration

### Data Source
- **Input:** Google Sheets "Autoequity" worksheet
- **Columns:** Fecha (A), Número de teléfono (F), Agente (B), Asset ID (C), Nombre (D), Correo (E)
- **Filter:** Last 30 days from "Fecha Instalación GPS"

### Conversation Analysis
- **Source:** BigQuery conversation data
- **Filter:** Formalization phase only (regex: "y estaré acompañándote en esta última parte del proceso")
- **Analysis:** 5 structured questions + overall summary

### Output Destination
- **Local:** CSV files in `output_run/formalizacion/`
- **Remote:** Google Sheets "Bot Live" worksheet (auto-uploaded)

## 📈 Expected Results

- **Total leads:** ~210 (from Google Sheets)
- **With conversations:** ~44 (analyzed)
- **Without conversations:** ~166 (marked as "Sin conversación registrada")
- **Processing time:** ~2-3 minutes
- **Output:** Clean, actionable data ready for decision making

## 🆘 Troubleshooting

### Google Sheets Upload Fails
- Check credentials file: `/Users/isaacentebi/Desktop/Kavak Capital Service Account.json`
- Verify sheet access permissions
- Manual upload: Use the generated CSV file

### No Conversation Data
- Normal for leads without formalization conversations
- Check BigQuery connection if all leads show "Sin conversación registrada"

### Module Import Errors
- Use the clean solution: `run_clean_formalizacion.py`
- Avoid the standard recipe if you have import issues

## 🎯 Success Metrics

✅ **Clean output:** 12 essential columns only  
✅ **Smart summaries:** Actionable insights for each lead  
✅ **Real data:** Agent names, asset IDs, client information  
✅ **Auto-upload:** Results in Google Sheets immediately  
✅ **Ready to use:** No additional processing needed

---

**Recommended Command:** `python3 run_clean_formalizacion.py`  
**Output File:** `output_run/formalizacion/latest_clean.csv`  
**Google Sheets:** "Bot Live" worksheet (auto-updated) 