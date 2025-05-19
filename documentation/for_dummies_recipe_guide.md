# Lead Recovery Recipe Creation and Maintenance: FOR DUMMIES

This guide is for non-technical users and LLM agents. It explains, step by step, how to create, validate, and run recipes in the Lead Recovery system—**no coding required!**

---

## 1. Creating a New Recipe (The Easy Way)

1. Open a terminal and run:
   ```bash
   python create_recipe.py
   ```
2. Answer the friendly questions:
   - **Name:** What do you want to call your recipe? (e.g., `my_new_recipe`)
   - **Description:** What does this recipe do? (one sentence)
   - **Processors:** Pick from a numbered list (e.g., 1,2,5). Each processor has a short description.
   - **LLM Output:** What should the AI output? (Choose from suggestions or type your own, separated by commas)
   - **Lead Info Columns:** Do you want extra info like phone, name, etc.? (Y/N)
3. That's it! Your recipe is created in `recipes/<your_recipe_name>/` with all the files you need.

---

## 2. Validating Your Recipe

After creating or editing a recipe, always validate it:
```bash
python scripts/validate_all_recipes.py
```
Or, if you prefer:
```bash
python -m lead_recovery.cli.main validate-recipes
```
- If you see `[OK]`, you're good!
- If you see `[FAIL]`, read the message and fix your recipe (see below).

---

## 3. Running Your Recipe

To run your recipe and generate results:
```bash
python -m lead_recovery.cli.main run --recipe <your_recipe_name>
```
- Use `--limit 1` for a quick test.
- Use `--skip-redshift --skip-bigquery` if you want to use existing data.

---

## 4. Adding or Removing Processors (Flags)

- **To add a processor:**
  1. Edit your recipe's `meta.yml`.
  2. Add the processor to the `python_processors` list (copy from another recipe or use the generator).
  3. Run:
     ```bash
     python -m lead_recovery.cli.main update-output-columns <your_recipe_name>
     ```
  4. Validate your recipe.

- **To remove a processor:**
  1. Remove it from `python_processors`.
  2. Run the update-output-columns command.
  3. Validate your recipe.

---

## 5. Adding or Removing LLM Output Keys

- **To add a key:**
  1. Edit `llm_config.expected_llm_keys` in meta.yml.
  2. Run the update-output-columns command.
  3. Validate your recipe.

- **To remove a key:**
  1. Remove it from `expected_llm_keys`.
  2. Run the update-output-columns command.
  3. Validate your recipe.

---

## 6. Troubleshooting

- **Validation fails for a column:**
  - Make sure the column is produced by a processor, LLM key, or is a lead info column.
  - If you're not sure, run the update-output-columns command.
- **Output column missing in CSV:**
  - Make sure the processor is active and the column is in `GENERATED_COLUMNS`.
  - Make sure the column is in `output_columns`.
- **Still stuck?**
  - Ask an LLM agent or a technical team member for help!

---

## 7. For LLM Agents: How to Help Users

- Always use the interactive recipe generator for new recipes.
- Use the update-output-columns CLI to keep output_columns in sync.
- Validate recipes after any change.
- If a user wants to add/remove a processor or LLM key, follow the steps above.
- If validation fails, read the error and suggest the fix.
- Never edit output_columns by hand—use the tool!

---

## 8. Example: Creating and Running a Recipe

```bash
python create_recipe.py
# (answer prompts)
python scripts/validate_all_recipes.py
python -m lead_recovery.cli.main run --recipe my_new_recipe --limit 1
```

---

**You don't need to know Python. Just follow the steps and you'll be a recipe pro!** 