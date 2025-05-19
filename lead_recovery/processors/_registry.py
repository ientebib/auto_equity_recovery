"""
Processor Registry for Lead Recovery

This module provides a central registry of all processor classes and their GENERATED_COLUMNS.
Processors should register themselves on import.
"""

PROCESSOR_REGISTRY = {}

def register_processor(cls):
    PROCESSOR_REGISTRY[cls.__name__] = getattr(cls, 'GENERATED_COLUMNS', [])
    return cls

def get_columns_for_processor(processor_name: str):
    return PROCESSOR_REGISTRY.get(processor_name, []) 