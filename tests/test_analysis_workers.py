import logging

import pandas as pd
import pytest

from lead_recovery import analysis


class DummySummarizer:
    def __init__(self, *args, **kwargs):
        pass

    async def summarize(self, conv_df, temporal_flags=None):
        return {"summary": "ok"}


class DummyValidator:
    def __init__(self, *args, **kwargs):
        pass

    def fix_yaml(self, data, temporal_flags=None):
        return data


@pytest.mark.asyncio
async def test_process_conversations_default_workers(monkeypatch, caplog):
    convos_df = pd.DataFrame(
        {
            "creation_time": ["2024-01-01T00:00:00", "2024-01-01T00:01:00"],
            "msg_from": ["user", "bot"],
            "message": ["hi", "hello"],
            analysis.CLEANED_PHONE_COLUMN_NAME: ["1234567890", "1234567890"],
        }
    )

    monkeypatch.setattr(analysis, "ConversationSummarizer", DummySummarizer)
    monkeypatch.setattr(analysis, "YamlValidator", DummyValidator)

    caplog.set_level(logging.INFO)

    summaries, errors = await analysis._process_conversations(
        convos_df,
        None,
        None,
        None,
        False,
        {},
        {},
        None,
        None,
    )

    assert not errors
    worker_logs = [r for r in caplog.records if "Using max_workers" in r.getMessage()]
    assert worker_logs
    msg = worker_logs[0].getMessage()
    count = int(msg.split("=")[1].split()[0])
    assert count > 0
