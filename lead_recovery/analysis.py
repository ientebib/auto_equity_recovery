"""analysis.py
Core orchestration module for the lead recovery pipeline.

This module is responsible for orchestrating the entire lead processing flow:
1. Loading data from conversations and leads
2. Running all configured processors via ProcessorRunner
3. Calling the LLM via ConversationSummarizer
4. Validating and fixing outputs via YamlValidator
5. Writing results to output files
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .cache import SummaryCache, compute_conversation_digest
from .config import settings
from .constants import (
    CLEANED_PHONE_COLUMN_NAME,
    MESSAGE_COLUMN_NAME,
)
from .exceptions import ApiError, LeadRecoveryError, RecipeConfigurationError, ValidationError
from .fs import update_link
from .gsheets import upload_to_google_sheets
from .processor_runner import ProcessorRunner
from .reporting import export_data
from .summarizer import ConversationSummarizer
from .utils import log_memory_usage, optimize_dataframe
from .yaml_validator import YamlValidator

logger = logging.getLogger(__name__)

# Define missing constant
SENDER_COLUMN_NAME = "msg_from"


def _load_input_data(output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and normalise conversation and lead data from ``output_dir``."""
    conversations_file = output_dir / "conversations.csv"
    leads_file = output_dir / "leads.csv"

    if not conversations_file.exists():
        raise LeadRecoveryError("Conversations file not found. Run fetch-convos first.")
    if not leads_file.exists():
        raise LeadRecoveryError("Leads file not found. Run fetch-convos first.")

    convos_reader = pd.read_csv(conversations_file, chunksize=100000)
    convos_df = pd.concat(convos_reader, ignore_index=True)
    convos_df = optimize_dataframe(convos_df)

    leads_df = pd.read_csv(leads_file)
    leads_df = optimize_dataframe(leads_df)

    if "cleaned_phone_number" in convos_df.columns and CLEANED_PHONE_COLUMN_NAME not in convos_df.columns:
        convos_df.rename(columns={"cleaned_phone_number": CLEANED_PHONE_COLUMN_NAME}, inplace=True)

    def _norm(series: pd.Series) -> pd.Series:
        s = series.astype(str).str.strip()
        return s.str.extract(r"(\d{10})")[0]

    leads_df[CLEANED_PHONE_COLUMN_NAME] = _norm(leads_df[CLEANED_PHONE_COLUMN_NAME])
    convos_df[CLEANED_PHONE_COLUMN_NAME] = _norm(convos_df[CLEANED_PHONE_COLUMN_NAME])

    leads_df.dropna(subset=[CLEANED_PHONE_COLUMN_NAME], inplace=True)
    convos_df.dropna(subset=[CLEANED_PHONE_COLUMN_NAME], inplace=True)

    if CLEANED_PHONE_COLUMN_NAME not in convos_df.columns and not convos_df.empty:
        raise ValueError(f"Conversation data missing required column: {CLEANED_PHONE_COLUMN_NAME}")

    if not convos_df.empty:
        required_cols = {"creation_time", "msg_from", MESSAGE_COLUMN_NAME, CLEANED_PHONE_COLUMN_NAME}
        missing = required_cols - set(convos_df.columns)
        if missing:
            raise LeadRecoveryError(f"Conversation data missing required columns: {missing}")

    logger.info("Loaded %d conversation messages and %d leads", len(convos_df), len(leads_df))

    return convos_df, leads_df


async def _process_conversations(
    convos_df: pd.DataFrame,
    processor_runner: ProcessorRunner | None,
    prompt_template_path: Path | None,
    max_workers: int | None,
    use_cache: bool,
    cached_results: dict[str, dict],
    conversation_digests: dict[str, str],
    meta_config: dict | None,
    limit: int | None = None,
) -> tuple[dict[str, dict], dict[str, str]]:
    """Run the async summarization loop for each phone number."""

    phone_groups = convos_df.groupby(CLEANED_PHONE_COLUMN_NAME)
    if limit is not None and limit > 0:
        phone_numbers = list(phone_groups.groups.keys())[:limit]
        convos_df = convos_df[convos_df[CLEANED_PHONE_COLUMN_NAME].isin(phone_numbers)]
        phone_groups = convos_df.groupby(CLEANED_PHONE_COLUMN_NAME)

    summarizer = ConversationSummarizer(
        prompt_template_path=prompt_template_path,
        use_cache=use_cache,
        meta_config=meta_config,
    )
    validator = YamlValidator(meta_config=meta_config)

    if max_workers is None or max_workers <= 0:
        max_workers = min(32, max(4, os.cpu_count() or 4))
    logger.info("Using max_workers=%s for concurrent processing", max_workers)

    summaries: dict[str, dict] = {}
    errors: dict[str, str] = {}
    total = len(phone_groups)
    completed = 0
    semaphore = asyncio.Semaphore(max_workers)

    async def process(phone: str, group: pd.DataFrame) -> None:
        nonlocal completed
        max_retries = 3
        retry_delay = 5
        attempt = 0
        acquired = False
        while attempt < max_retries:
            attempt += 1
            try:
                try:
                    await asyncio.wait_for(semaphore.acquire(), timeout=300)
                    acquired = True
                except asyncio.TimeoutError:
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay)
                        continue
                    summaries[phone] = {
                        "summary": "ERROR: Timed out waiting to acquire processing slot after retries.",
                        "inferred_stall_stage": "ERROR_TIMEOUT",
                        "primary_stall_reason_code": "ERROR_SEMAPHORE_TIMEOUT",
                        "next_action_code": "ERROR_RETRY_FAILED",
                    }
                    break

                convo_text = "\n".join(
                    f"{getattr(row, 'creation_time', '')[:19]} {getattr(row, SENDER_COLUMN_NAME, '')}: {getattr(row, MESSAGE_COLUMN_NAME, '')}"
                    for row in group.itertuples(index=False)
                )
                digest = compute_conversation_digest(convo_text)
                if use_cache and phone in cached_results:
                    if conversation_digests.get(phone) == digest:
                        summaries[phone] = cached_results[phone]
                        break

                proc_results = {}
                if processor_runner is not None:
                    try:
                        lead_data = pd.Series({"phone": phone}, name=phone)
                        proc_results = processor_runner.run_all(lead_data=lead_data, conversation_data=group, initial_results={})
                    except Exception as e:  # noqa: BLE001
                        logger.error("Error running processors for %s: %s", phone, e, exc_info=True)
                        proc_results = {}

                llm_result = await summarizer.summarize(group.copy(), temporal_flags=proc_results)
                validated = validator.fix_yaml(llm_result, temporal_flags=proc_results)
                if validated is None:
                    summaries[phone] = {
                        "summary": "ERROR: LLM summarization failed.",
                        "inferred_stall_stage": "ERROR_LLM_NONE",
                        "primary_stall_reason_code": "ERROR_LLM_NONE",
                        "next_action_code": "ERROR_LLM_NONE",
                    }
                    summaries[phone].update(proc_results)
                else:
                    combined = {**validated, **proc_results}
                    combined[CLEANED_PHONE_COLUMN_NAME] = phone
                    combined["conversation_digest"] = digest
                    combined["cache_status"] = "FRESH"
                    summaries[phone] = combined
                break
            except (ApiError, ValidationError) as e:
                errors[phone] = str(e)
                summaries[phone] = {
                    "summary": f"ERROR: {type(e).__name__} during processing.",
                    "error_details": str(e),
                    "inferred_stall_stage": "ERROR_PROCESSING",
                    "primary_stall_reason_code": "ERROR_PROCESSING",
                    "next_action_code": "ERROR_PROCESSING",
                }
                break
            except Exception as e:  # noqa: BLE001
                errors[phone] = f"Unexpected error: {e}"
                summaries[phone] = {
                    "summary": f"ERROR: Unexpected {type(e).__name__}.",
                    "error_details": str(e),
                    "inferred_stall_stage": "ERROR_UNEXPECTED",
                    "primary_stall_reason_code": "ERROR_UNEXPECTED",
                    "next_action_code": "ERROR_UNEXPECTED",
                }
                break
            finally:
                if acquired:
                    semaphore.release()
                    acquired = False
        completed += 1
        if completed % 10 == 0 or completed == total:
            logger.info("Progress: %d/%d (%.1f%%)", completed, total, completed / total * 100)

    await asyncio.gather(*(process(phone, grp) for phone, grp in phone_groups))

    return summaries, errors


def _merge_results(
    leads_df: pd.DataFrame,
    summaries: dict[str, dict],
    errors: dict[str, str],
) -> pd.DataFrame:
    """Merge lead information with processor summaries and errors efficiently."""

    result_df = leads_df.copy()

    if summaries:
        summaries_df = (
            pd.DataFrame.from_dict(summaries, orient="index")
            .rename_axis(CLEANED_PHONE_COLUMN_NAME)
            .reset_index()
        )
        result_df = result_df.merge(
            summaries_df, on=CLEANED_PHONE_COLUMN_NAME, how="left"
        )

    if errors:
        errors_df = pd.DataFrame(
            list(errors.items()),
            columns=[CLEANED_PHONE_COLUMN_NAME, "error"],
        )
        result_df = result_df.merge(errors_df, on=CLEANED_PHONE_COLUMN_NAME, how="left")

    if "summary" not in result_df.columns:
        result_df["summary"] = "No conversation data found"
    else:
        result_df["summary"] = result_df["summary"].fillna("No conversation data found")

    return optimize_dataframe(result_df)


def _export_results(
    result_df: pd.DataFrame,
    output_dir: Path,
    recipe_name: str | None,
    meta_config: dict | None,
) -> dict[str, Path]:
    today_str = datetime.now().strftime("%Y%m%d")
    base_name = f"{recipe_name}_analysis_{today_str}" if recipe_name else f"analysis_{today_str}"

    export_formats = ["csv"]
    if meta_config and isinstance(meta_config, dict) and "export_formats" in meta_config:
        cfg = meta_config["export_formats"]
        if isinstance(cfg, list):
            for fmt in cfg:
                if fmt.lower() in ["json"] and fmt.lower() not in export_formats:
                    export_formats.append(fmt.lower())
        elif isinstance(cfg, str) and cfg.lower() in ["json", "all"]:
            if cfg.lower() == "all":
                export_formats = ["csv", "json"]
            elif cfg.lower() not in export_formats:
                export_formats.append(cfg.lower())

    export_data(result_df, output_dir, base_name, export_formats)

    run_ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H-%M")
    run_dir = output_dir / run_ts
    run_dir.mkdir(parents=True, exist_ok=True)
    dated_paths = export_data(result_df, run_dir, "analysis", export_formats)

    if "csv" in dated_paths:
        update_link(dated_paths["csv"], output_dir / "latest.csv")
    if "json" in dated_paths:
        update_link(dated_paths["json"], output_dir / "latest.json")

    return dated_paths


async def run_summarization_step(
    output_dir: Path,
    prompt_template_path: Optional[Path] = None,
    max_workers: Optional[int] = None,
    recipe_name: Optional[str] = None,
    use_cache: bool = True,
    gsheet_config: Optional[Dict[str, str]] = None,
    meta_config: Optional[Dict[str, Any]] = None,
    include_columns: Optional[List[str]] = None,
    exclude_columns: Optional[List[str]] = None,
    skip_detailed_temporal_calc: bool = False,
    skip_hours_minutes: bool = False,
    skip_reactivation_flags: bool = False,
    skip_timestamps: bool = False,
    skip_user_message_flag: bool = False,
    skip_handoff_detection: bool = False,
    skip_metadata_extraction: bool = False,
    skip_handoff_invitation: bool = False,
    skip_handoff_started: bool = False,
    skip_handoff_finalized: bool = False,
    skip_human_transfer: bool = False,
    skip_recovery_template_detection: bool = False,
    skip_consecutive_templates_count: bool = False,
    skip_pre_validacion_detection: bool = False,
    skip_conversation_state: bool = False,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """Orchestrate the summarization pipeline."""

    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        cache = None
        cached_results: dict[str, dict] = {}
        conversation_digests: dict[str, str] = {}
        if use_cache:
            cache = SummaryCache(output_dir)
            if hasattr(cache, "load_all_cached_results"):
                cached_results = cache.load_all_cached_results()
                conversation_digests = {k: v.get("conversation_digest", "") for k, v in cached_results.items()}

        logger.info("--- Skip Flag Configuration ---")
        logger.info(f"skip_detailed_temporal_calc = {skip_detailed_temporal_calc}")
        logger.info(f"skip_hours_minutes = {skip_hours_minutes}")
        logger.info(f"skip_reactivation_flags = {skip_reactivation_flags}")
        logger.info(f"skip_timestamps = {skip_timestamps}")
        logger.info(f"skip_user_message_flag = {skip_user_message_flag}")
        logger.info(f"skip_handoff_detection = {skip_handoff_detection}")
        logger.info(f"skip_metadata_extraction = {skip_metadata_extraction}")
        logger.info(f"skip_handoff_invitation = {skip_handoff_invitation}")
        logger.info(f"skip_handoff_started = {skip_handoff_started}")
        logger.info(f"skip_handoff_finalized = {skip_handoff_finalized}")
        logger.info(f"skip_human_transfer = {skip_human_transfer}")
        logger.info(f"skip_recovery_template_detection = {skip_recovery_template_detection}")
        logger.info(f"skip_consecutive_templates_count = {skip_consecutive_templates_count}")
        logger.info(f"skip_pre_validacion_detection = {skip_pre_validacion_detection}")
        logger.info(f"skip_conversation_state = {skip_conversation_state}")
        logger.info("---------------------------")

        if limit is None and meta_config and meta_config.get("limit") is not None:
            limit = meta_config["limit"]
            logger.info(f"Using conversation limit from meta_config: {limit}")

        processor_runner = None
        if recipe_name:
            if not (meta_config and isinstance(meta_config, dict) and meta_config.get("python_processors") is not None):
                raise RecipeConfigurationError("Invalid or missing meta_config in analysis.py")
            processor_runner = ProcessorRunner(recipe_config=meta_config)

        output_columns = meta_config.get("output_columns") if meta_config and "output_columns" in meta_config else None

        log_memory_usage("Before loading data: ")
        convos_df, leads_df = _load_input_data(output_dir)

        if convos_df.empty:
            result_df = leads_df.copy()
            result_df["summary"] = "No conversation data available"
            _export_results(result_df, output_dir, recipe_name, meta_config)
            return result_df

        summaries, errors = await _process_conversations(
            convos_df,
            processor_runner,
            prompt_template_path,
            max_workers,
            use_cache,
            cached_results,
            conversation_digests,
            meta_config,
            limit,
        )

        log_memory_usage("After processing all conversations: ")

        result_df = _merge_results(leads_df, summaries, errors)

        include_cols = meta_config.get("include_columns", []) if meta_config else []
        exclude_cols = meta_config.get("exclude_columns", []) if meta_config else []
        if include_columns:
            include_cols = include_columns
        if exclude_columns:
            exclude_cols = exclude_columns

        if include_cols:
            essential = {CLEANED_PHONE_COLUMN_NAME}
            cols_to_include = [c for c in include_cols if c in result_df.columns]
            for col in essential:
                if col not in cols_to_include and col in result_df.columns:
                    cols_to_include.insert(0, col)
            result_df = result_df[cols_to_include]
        if exclude_cols:
            cols_to_exclude = [c for c in exclude_cols if c != CLEANED_PHONE_COLUMN_NAME]
            result_df = result_df.drop(columns=cols_to_exclude, errors="ignore")

        if output_columns:
            for col in output_columns:
                if col not in result_df.columns:
                    result_df[col] = ""

        dated_paths = _export_results(result_df, output_dir, recipe_name, meta_config)
        run_dir = next(iter(dated_paths.values())).parent if dated_paths else output_dir

        if errors:
            ignored_csv_path = run_dir / "ignored.csv"
            latest_ignored_path = output_dir / "latest_ignored.csv"
            error_rows = [
                {CLEANED_PHONE_COLUMN_NAME: p, "error": msg, "cache_status": "ERROR"}
                for p, msg in errors.items()
            ]
            pd.DataFrame(error_rows).to_csv(ignored_csv_path, index=False)
            update_link(ignored_csv_path, latest_ignored_path)

        if use_cache and cache:
            cache_records = [d for d in summaries.values() if "conversation_digest" in d]
            if cache_records:
                pd.DataFrame(cache_records).to_csv(output_dir / "cache.csv", index=False)

        if gsheet_config and isinstance(gsheet_config, dict):
            sheet_id = gsheet_config.get("sheet_id")
            worksheet_name = gsheet_config.get("worksheet_name")
            if sheet_id and worksheet_name:
                try:
                    credentials_path = settings.GOOGLE_CREDENTIALS_PATH
                    upload_path = dated_paths.get("json") or (output_dir / "latest.csv")
                    upload_to_google_sheets(upload_path, sheet_id, worksheet_name, credentials_path)
                except Exception as e:
                    logger.error("Error uploading to Google Sheets: %s", e)

        return result_df

    except Exception as e:
        logger.exception("Error in summarization step: %s", e)
        raise LeadRecoveryError(f"Summarization failed: {e}") from e

