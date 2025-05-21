# Duplicate of dashboard.utils.recipe_builder_helpers with path inside webui
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# PyYAML fallback
import yaml as _pyyaml

from lead_recovery.cli.update_output_columns import DEFAULT_LEAD_COLUMNS
from lead_recovery.processors._registry import PROCESSOR_REGISTRY

try:
    from ruamel.yaml import YAML as _RuYAML
    YAML = _RuYAML
except ImportError:
    YAML = None

yaml = _pyyaml


def load_meta_yml(recipe_path: Path) -> Dict[str, Any]:
    meta_path = recipe_path / "meta.yml"
    if YAML:
        with open(meta_path, "r") as f:
            return YAML.load(f)
    else:
        with open(meta_path, "r") as f:
            return yaml.safe_load(f)

def save_meta_yml(recipe_path: Path, data: Dict[str, Any]):
    meta_path = recipe_path / "meta.yml"
    backup_file(meta_path)
    if YAML:
        with open(meta_path, "w") as f:
            YAML.dump(data, f)
    else:
        with open(meta_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)

def backup_file(path: Path):
    if path.exists():
        ts = datetime.now().strftime("~%Y-%m-%dT%H-%M-%S.bak")
        shutil.copy2(path, path.with_name(path.name + ts))

def extract_yaml_keys_from_prompt(prompt_text: str) -> List[str]:
    block_match = re.search(r"```yaml(.*?)```", prompt_text, re.DOTALL)
    if not block_match:
        return []
    block = block_match.group(1)
    return [k.strip() for k in re.findall(r"^\s*([A-Za-z0-9_\-]+):", block, re.MULTILINE)]

def list_processors():
    processors = []
    for name, cols in PROCESSOR_REGISTRY.items():
        try:
            mod = __import__(f"lead_recovery.processors.{name.lower()}", fromlist=[name])
            cls = getattr(mod, name)
            desc = (cls.__doc__ or "").strip().split("\n")[0]
        except Exception:
            desc = ""
        processors.append({"name": name, "description": desc, "columns": cols})
    return processors

def list_default_lead_columns() -> List[str]:
    return list(DEFAULT_LEAD_COLUMNS) 