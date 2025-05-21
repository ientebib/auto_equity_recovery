import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

# Ensure webui path is on sys.path
sys.path.append(str(Path(__file__).parent))
from lead_recovery.cli.update_output_columns import update_output_columns
from lead_recovery.recipe_schema import RecipeMeta
from webui.utils.recipe_builder_helpers import (
    extract_yaml_keys_from_prompt,
    list_default_lead_columns,
    list_processors,
    load_meta_yml,
    save_meta_yml,
)

RECIPES_DIR = Path(__file__).parent.parent / "recipes"
DOC_PATH = Path(__file__).parent.parent / "documentation/for_dummies_recipe_guide.md"

st.set_page_config(page_title="Recipe Builder", page_icon="🛠️", layout="wide")

st.title("🛠️ Lead Recovery Recipe Builder")

st.markdown("""
Welcome to the new Lead Recovery Recipe Builder!

- This tool will let you create, edit, and validate recipes without any technical knowledge.
- All changes are safely backed up and validated before saving.

[📖 User Guide](../documentation/for_dummies_recipe_guide.md)
""")

# --- Clone Recipe Feature ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 🧬 Clone Recipe")
clone_recipe = st.sidebar.checkbox("Clone an Existing Recipe")
if clone_recipe:
    recipe_dirs = [d for d in RECIPES_DIR.iterdir() if d.is_dir() and (d / "meta.yml").exists()]
    recipe_names = [d.name for d in recipe_dirs]
    recipe_to_clone = st.sidebar.selectbox("Select recipe to clone", ["-"] + recipe_names)
    new_recipe_name = st.sidebar.text_input("New recipe name (for clone)")
    if st.sidebar.button("Clone Now", disabled=not (recipe_to_clone and recipe_to_clone != "-" and new_recipe_name)):
        meta = load_meta_yml(RECIPES_DIR / recipe_to_clone)
        st.session_state.step = 1
        st.session_state.recipe_metadata = {
            "recipe_name": new_recipe_name.strip(),
            "description": meta.get("description", ""),
            "author": meta.get("author", ""),
        }
        st.session_state.selected_processors = [
            proc["module"].split(".")[-1] for proc in meta.get("python_processors", []) if isinstance(proc, dict) and "module" in proc
        ]
        st.session_state.processor_params = {
            proc["module"].split(".")[-1]: proc.get("params", {}) for proc in meta.get("python_processors", []) if isinstance(proc, dict) and "module" in proc
        }
        st.session_state.llm_keys = list(meta.get("llm_config", {}).get("expected_llm_keys", {}).keys())
        st.session_state.lead_columns = meta.get("lead_columns", list_default_lead_columns())
        data_input = meta.get("data_input", {})
        st.session_state.data_source_type = data_input.get("lead_source_type", "redshift")
        st.session_state.redshift_sql_file = data_input.get("redshift_config", {}).get("sql_file", "redshift.sql")
        st.session_state.csv_file = data_input.get("csv_config", {}).get("csv_file", "leads.csv")
        prompt_path = RECIPES_DIR / recipe_to_clone / "prompt.txt"
        st.session_state.prompt_text = prompt_path.read_text() if prompt_path.exists() else ""
        readme_path = RECIPES_DIR / recipe_to_clone / "README.md"
        st.session_state.readme_text = readme_path.read_text() if readme_path.exists() else ""
        redshift_path = RECIPES_DIR / recipe_to_clone / "redshift.sql"
        st.session_state.redshift_sql = redshift_path.read_text() if redshift_path.exists() else ""
        bigquery_path = RECIPES_DIR / recipe_to_clone / "bigquery.sql"
        st.session_state.bigquery_sql = bigquery_path.read_text() if bigquery_path.exists() else ""
        st.session_state.edit_loaded = None
        st.experimental_rerun()

# --- Edit Existing Recipe Mode ---
recipe_dirs = [d for d in RECIPES_DIR.iterdir() if d.is_dir() and (d / "meta.yml").exists()]
recipe_names = [d.name for d in recipe_dirs]

edit_mode = st.sidebar.checkbox("Edit Existing Recipe")
selected_recipe = None
if edit_mode:
    selected_recipe = st.sidebar.selectbox("Select a recipe to edit", ["-"] + recipe_names)
    if selected_recipe and selected_recipe != "-":
        # Load meta.yml and prefill session state
        meta = load_meta_yml(RECIPES_DIR / selected_recipe)
        if 'step' not in st.session_state or st.session_state.get('edit_loaded') != selected_recipe:
            st.session_state.step = 1
            st.session_state.recipe_metadata = {
                "recipe_name": meta.get("recipe_name", selected_recipe),
                "description": meta.get("description", ""),
                "author": meta.get("author", ""),
            }
            st.session_state.selected_processors = [
                proc["module"].split(".")[-1] for proc in meta.get("python_processors", []) if isinstance(proc, dict) and "module" in proc
            ]
            st.session_state.processor_params = {
                proc["module"].split(".")[-1]: proc.get("params", {}) for proc in meta.get("python_processors", []) if isinstance(proc, dict) and "module" in proc
            }
            st.session_state.llm_keys = list(meta.get("llm_config", {}).get("expected_llm_keys", {}).keys())
            st.session_state.lead_columns = meta.get("lead_columns", list_default_lead_columns())
            # Data input
            data_input = meta.get("data_input", {})
            st.session_state.data_source_type = data_input.get("lead_source_type", "redshift")
            st.session_state.redshift_sql_file = data_input.get("redshift_config", {}).get("sql_file", "redshift.sql")
            st.session_state.csv_file = data_input.get("csv_config", {}).get("csv_file", "leads.csv")
            # Load prompt.txt if exists
            prompt_path = RECIPES_DIR / selected_recipe / "prompt.txt"
            if prompt_path.exists():
                st.session_state.prompt_text = prompt_path.read_text()
            else:
                st.session_state.prompt_text = ""
            # Load README.md and SQL files if exist
            readme_path = RECIPES_DIR / selected_recipe / "README.md"
            st.session_state.readme_text = readme_path.read_text() if readme_path.exists() else ""
            redshift_path = RECIPES_DIR / selected_recipe / "redshift.sql"
            st.session_state.redshift_sql = redshift_path.read_text() if redshift_path.exists() else ""
            bigquery_path = RECIPES_DIR / selected_recipe / "bigquery.sql"
            st.session_state.bigquery_sql = bigquery_path.read_text() if bigquery_path.exists() else ""
            st.session_state.edit_loaded = selected_recipe

# --- Step 1: Metadata ---
if 'step' not in st.session_state:
    st.session_state.step = 1

if st.session_state.step == 1:
    st.header("Step 1: Recipe Metadata")
    st.write("Enter the basic information for your new recipe.\n\n- The name must be unique and use only letters, numbers, and underscores.\n- The description should be a single sentence for easy searching.\n- The author is pre-filled from your system user.")
    # Prefill if editing
    recipe_name = st.text_input(
        "Recipe Name (letters, numbers, underscores only)",
        value=st.session_state.get("recipe_metadata", {}).get("recipe_name", ""),
        help="Unique name for this recipe."
    )
    description = st.text_area(
        "Description",
        value=st.session_state.get("recipe_metadata", {}).get("description", ""),
        help="Describe what this recipe does."
    )
    author = st.text_input(
        "Author",
        value=st.session_state.get("recipe_metadata", {}).get("author", os.environ.get("USER", "Unknown")),
        help="Recipe creator."
    )
    # Basic validation
    valid_name = recipe_name and recipe_name.replace('_', '').isalnum()
    name_error = None
    if recipe_name and not valid_name:
        name_error = "Recipe name must only contain letters, numbers, and underscores."
        st.error(name_error)
    if st.button("Next", disabled=not (valid_name and description and author)):
        st.session_state.recipe_metadata = {
            "recipe_name": recipe_name.strip(),
            "description": description.strip(),
            "author": author.strip(),
        }
        st.session_state.step = 2
        st.experimental_rerun()

# --- Step 2: Data Source Selection ---
if st.session_state.step == 2:
    st.header("Step 2: Data Source Selection")
    st.write("Choose how to provide leads data.\n\n- Conversations are always extracted from BigQuery.\n- Leads can come from a Redshift SQL query or a CSV file.\n- If using CSV, upload or specify the file name.\n- If using Redshift, specify the SQL file name (default: redshift.sql).\n")
    data_source_type = st.radio(
        "Leads Data Source",
        options=["redshift", "csv"],
        index=0 if st.session_state.get("data_source_type", "redshift") == "redshift" else 1,
        format_func=lambda x: "Redshift SQL" if x == "redshift" else "Leads CSV"
    )
    st.session_state.data_source_type = data_source_type
    if data_source_type == "redshift":
        redshift_sql_file = st.text_input("Redshift SQL file name", value=st.session_state.get("redshift_sql_file", "redshift.sql"), help="File name for the Redshift SQL query.")
        st.session_state.redshift_sql_file = redshift_sql_file
    else:
        csv_file = st.text_input("Leads CSV file name", value=st.session_state.get("csv_file", "leads.csv"), help="File name for the leads CSV.")
        st.session_state.csv_file = csv_file
    if st.button("Next"):
        st.session_state.step = 3
        st.experimental_rerun()
    if st.button("Back"):
        st.session_state.step = 1
        st.experimental_rerun()

# --- Step 3: Processor Selection ---
if 'processor_list' not in st.session_state:
    st.session_state.processor_list = list_processors()
processors = st.session_state.processor_list

if st.session_state.step == 3:
    st.header("Step 3: Processor Selection")
    st.write("Select the processors to include in your recipe.\n\n- Each processor adds columns to your output.\n- You can edit parameters for each processor in JSON format.\n- Hover over processor names for descriptions.\n")
    processor_names = [p['name'] for p in processors]
    default_selected = st.session_state.get("selected_processors", [])
    selected = st.multiselect(
        "Processors",
        options=processor_names,
        default=default_selected,
        help="Choose one or more processors."
    )
    st.session_state.selected_processors = selected
    # Processor params
    if 'processor_params' not in st.session_state:
        st.session_state.processor_params = {name: {} for name in selected}
    processor_errors = {}
    for name in selected:
        st.markdown(f"**{name} parameters (JSON):**")
        default_json = json.dumps(st.session_state.processor_params.get(name, {}), indent=2)
        param_str = st.text_area(f"Params for {name}", value=default_json, key=f"params_{name}", help="Edit processor parameters as JSON.")
        try:
            st.session_state.processor_params[name] = json.loads(param_str)
        except Exception:
            st.warning(f"Invalid JSON for {name}, using empty dict.")
            st.session_state.processor_params[name] = {}
        # Validate processor params by instantiating the processor class
        try:
            # Import processor class
            mod = importlib.import_module(f"lead_recovery.processors.{name.lower()}")
            cls = getattr(mod, name)
            # Dummy RecipeMeta and global_config
            dummy_meta = RecipeMeta(
                recipe_schema_version=2,
                recipe_name="dummy",
                version="1.0",
                description="dummy",
                data_input={"lead_source_type": "redshift", "redshift_config": {"sql_file": "dummy.sql"}},
                python_processors=[],
                output_columns=[]
            )
            _ = cls(dummy_meta, st.session_state.processor_params[name], global_config={})
        except Exception as e:
            processor_errors[name] = str(e)
            st.error(f"Error in {name} params: {e}")
    # Show columns generated by selected processors
    if selected:
        st.subheader("Columns generated by selected processors:")
        for proc in processors:
            if proc['name'] in selected:
                st.markdown(f"**{proc['name']}**: {', '.join(proc['columns']) if proc['columns'] else 'No columns'}")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back"):
            st.session_state.step = 2
            st.experimental_rerun()
    with col2:
        if st.button("Next", disabled=not selected or any(processor_errors.values())):
            st.session_state.step = 4
            st.experimental_rerun()

# --- Step 4: LLM Keys and Lead Columns ---
elif st.session_state.step == 4:
    st.header("Step 4: LLM Keys and Lead Columns")
    st.write("Specify the LLM output keys and lead info columns for your recipe.\n\n- LLM keys are the fields the LLM will output in YAML.\n- Lead columns are extra info you want in your output (e.g., phone, name, etc.).\n- Use comma-separated values for LLM keys.\n")
    COMMON_LLM_KEYS = [
        "summary", "next_action_code", "lead_name", "current_stage", "primary_issue", "recommended_action", "suggested_followup_message"
    ]
    llm_keys = st.session_state.get("llm_keys", COMMON_LLM_KEYS)
    llm_keys_input = st.text_input(
        "LLM Output Keys (comma-separated)",
        value=", ".join(llm_keys) if isinstance(llm_keys, list) else llm_keys,
        help="Comma-separated list of YAML keys the LLM should output."
    )
    llm_keys_list = [k.strip() for k in llm_keys_input.split(",") if k.strip()]
    st.session_state.llm_keys = llm_keys_list
    default_lead_columns = list_default_lead_columns()
    lead_columns = st.session_state.get("lead_columns", default_lead_columns)
    lead_columns_selected = st.multiselect(
        "Lead Info Columns",
        options=default_lead_columns,
        default=lead_columns,
        help="Select columns to include from lead info."
    )
    st.session_state.lead_columns = lead_columns_selected
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back"):
            st.session_state.step = 3
            st.experimental_rerun()
    with col2:
        if st.button("Next", disabled=not (llm_keys_list and lead_columns_selected)):
            st.session_state.step = 5
            st.experimental_rerun()

# --- Step 5: Prompt Editor ---
elif st.session_state.step == 5:
    st.header("Step 5: Prompt Editor")
    st.write("Edit the prompt for the LLM.\n\n- The YAML keys in the prompt must match the LLM keys from the previous step.\n- Use triple backticks and 'yaml' for the YAML block.\n- The prompt guides the LLM's output format.\n")
    default_prompt = """You are analyzing conversations between customers and the support team.\n\nCONVERSATION:\n{conversation_text}\n\nPlease analyze the conversation and provide your results in the following YAML format:\n\n```yaml\nlead_name: The customer's full name from the conversation\nsummary: A brief summary of the conversation and current situation\ncurrent_stage: The current stage in the customer journey\nprimary_issue: The main problem or reason the customer is stalled\nrecommended_action: What should be done next with this lead\nsuggested_followup_message: A message we could send to re-engage this customer\n```\n\nDo not include any explanations or additional text outside the YAML block."""
    prompt_text = st.session_state.get("prompt_text", default_prompt)
    prompt = st.code_editor(prompt_text, language="yaml", height=300, key="prompt_editor")
    st.session_state.prompt_text = prompt
    extracted_keys = extract_yaml_keys_from_prompt(prompt)
    st.markdown(f"**YAML keys found in prompt:** {', '.join(extracted_keys) if extracted_keys else 'None'}")
    llm_keys_set = set(st.session_state.llm_keys)
    extracted_keys_set = set(extracted_keys)
    if llm_keys_set != extracted_keys_set:
        st.error(f"Mismatch between LLM keys ({', '.join(llm_keys_set)}) and YAML keys in prompt ({', '.join(extracted_keys_set)})!")
    else:
        st.success("LLM keys and YAML keys in prompt match.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back"):
            st.session_state.step = 4
            st.experimental_rerun()
    with col2:
        if st.button("Next", disabled=not (llm_keys_set == extracted_keys_set and extracted_keys)):
            st.session_state.step = 6
            st.experimental_rerun()

# --- Step 6: Review, Save, Validate ---
elif st.session_state.step == 6:
    st.header("Step 6: Review & Save Recipe")
    st.write("Review your recipe details below.\n\n- You can edit README and SQL files before saving.\n- After saving, the recipe will be validated.\n- Output columns are auto-generated and shown below.\n")
    st.subheader("README.md")
    readme_text = st.code_editor(st.session_state.get("readme_text", ""), language="markdown", height=150, key="readme_editor")
    st.session_state.readme_text = readme_text
    st.subheader("redshift.sql")
    redshift_sql = st.code_editor(st.session_state.get("redshift_sql", ""), language="sql", height=100, key="redshift_editor")
    st.session_state.redshift_sql = redshift_sql
    st.subheader("bigquery.sql")
    bigquery_sql = st.code_editor(st.session_state.get("bigquery_sql", ""), language="sql", height=100, key="bigquery_editor")
    st.session_state.bigquery_sql = bigquery_sql
    st.subheader("Metadata")
    st.json(st.session_state.recipe_metadata)
    st.subheader("Processors and Params")
    for proc in st.session_state.selected_processors:
        st.write(f"{proc}: {json.dumps(st.session_state.processor_params.get(proc, {}), indent=2)}")
    st.subheader("LLM Keys")
    st.write(st.session_state.llm_keys)
    st.subheader("Lead Columns")
    st.write(st.session_state.lead_columns)
    st.subheader("Prompt Preview")
    st.code(st.session_state.prompt_text, language="text")
    save_error = None
    save_success = None
    validation_result = None
    backup_status = None
    output_columns_preview = None
    if st.button("Save and Validate"):
        recipe_name = st.session_state.recipe_metadata["recipe_name"]
        recipe_dir = RECIPES_DIR / recipe_name
        recipe_dir.mkdir(parents=True, exist_ok=True)
        # Build data_input
        if st.session_state.data_source_type == "redshift":
            data_input = {
                "lead_source_type": "redshift",
                "redshift_config": {"sql_file": st.session_state.redshift_sql_file},
                "conversation_sql_file_bigquery": "bigquery.sql"
            }
        else:
            data_input = {
                "lead_source_type": "csv",
                "csv_config": {"csv_file": st.session_state.csv_file},
                "conversation_sql_file_bigquery": "bigquery.sql"
            }
        meta = {
            "recipe_schema_version": 2,
            "recipe_name": recipe_name,
            "version": "1.0",
            "description": st.session_state.recipe_metadata["description"],
            "data_input": data_input,
            "llm_config": {
                "expected_llm_keys": {k: {} for k in st.session_state.llm_keys},
                "prompt_file": "prompt.txt"
            },
            "python_processors": [
                {"module": f"lead_recovery.processors.{proc.lower()}.{proc}", "params": st.session_state.processor_params.get(proc, {})} for proc in st.session_state.selected_processors
            ],
            "lead_columns": st.session_state.lead_columns,
        }
        try:
            save_meta_yml(recipe_dir, meta)
            (recipe_dir / "prompt.txt").write_text(st.session_state.prompt_text)
            (recipe_dir / "README.md").write_text(st.session_state.readme_text)
            (recipe_dir / "redshift.sql").write_text(st.session_state.redshift_sql)
            (recipe_dir / "bigquery.sql").write_text(st.session_state.bigquery_sql)
            backup_status = "Backups created for previous files (if any)."
            update_output_columns(recipe_dir / "meta.yml", dry_run=False, backup=False)
            meta_after = load_meta_yml(recipe_dir)
            output_columns_preview = meta_after.get("output_columns", [])
            with st.spinner("Validating recipe..."):
                validation_cmd = [sys.executable, str(Path(__file__).parent.parent / "scripts/validate_all_recipes.py"), "--only", recipe_name]
                result = subprocess.run(validation_cmd, capture_output=True, text=True)
                validation_result = result.stdout + "\n" + result.stderr
            if result.returncode == 0:
                save_success = f"Recipe '{recipe_name}' saved and validated successfully!"
            else:
                save_error = "Validation failed! See output below."
        except Exception as e:
            save_error = str(e)
    if backup_status:
        st.info(backup_status)
    if output_columns_preview is not None:
        st.subheader("Final Output Columns (auto-generated)")
        st.write(output_columns_preview)
    if save_error:
        st.error(f"Error saving recipe: {save_error}")
    if save_success:
        st.success(save_success)
    if validation_result:
        st.subheader("Validation Output")
        st.code(validation_result, language="text")
    if st.button("Back"):
        st.session_state.step = 5
        st.experimental_rerun() 