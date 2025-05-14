# Recipe: fede_abril_preperfilamiento

This recipe is used for pre-profiling leads based on the logic defined in `prompt.txt`.

## Running the Recipe

This recipe assumes you already have a `leads.csv` file present in the corresponding output directory (`output_run/fede_abril_preperfilamiento/leads.csv`). Therefore, the Redshift step (which normally generates this file) should be skipped.

Use the following command from the project root directory:

```bash
lead-recovery run --recipe fede_abril_preperfilamiento --skip-redshift
```

This command will:
1.  Skip the Redshift query (`--skip-redshift`).
2.  Read the existing `leads.csv` from `output_run/fede_abril_preperfilamiento/`.
3.  Execute the BigQuery query defined in `bigquery.sql` to fetch conversations for the leads.
4.  Summarize the conversations using the OpenAI API and the prompt defined in `prompt.txt`.
5.  Generate the final analysis CSV and HTML reports in `output_run/fede_abril_preperfilamiento/`. 