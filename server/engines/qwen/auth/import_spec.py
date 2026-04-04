from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def get_import_spec() -> dict[str, Any]:
    """
    Get import credentials specification for Qwen Code.

    Returns specification for two optional files:
    - oauth_creds.json: Qwen OAuth credentials
    - settings.json: Qwen settings (including Coding Plan config)
    """
    return {
        "supported": True,
        "ask_user": {
            "kind": "upload_files",
            "files": [
                {
                    "name": "oauth_creds.json",
                    "required": False,
                    "accept": ".json",
                    "hint": "~/.qwen/oauth_creds.json",
                    "validator": "qwen_oauth_creds",
                },
                {
                    "name": "settings.json",
                    "required": False,
                    "accept": ".json",
                    "hint": "~/.qwen/settings.json",
                    "validator": "qwen_settings_coding_plan",
                },
            ],
        },
    }


def validate_oauth_creds(content: str) -> tuple[bool, str]:
    """
    Validate oauth_creds.json content.

    Must contain access_token or refresh_token.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"

    if not isinstance(data, dict):
        return False, "Expected JSON object"

    has_access = (
        "access_token" in data
        and isinstance(data["access_token"], str)
        and data["access_token"]
    )
    has_refresh = (
        "refresh_token" in data
        and isinstance(data["refresh_token"], str)
        and data["refresh_token"]
    )

    if not (has_access or has_refresh):
        return False, "Must contain access_token or refresh_token"

    return True, ""


def validate_settings_coding_plan(content: str) -> tuple[bool, str]:
    """
    Validate settings.json contains Coding Plan configuration.

    Checks for:
    - modelProviders.openai[] with Coding Plan endpoints
    - OR env.BAILIAN_CODING_PLAN_API_KEY
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"

    if not isinstance(data, dict):
        return False, "Expected JSON object"

    # Check for Coding Plan API key in env
    env = data.get("env", {})
    if isinstance(env, dict) and env.get("BAILIAN_CODING_PLAN_API_KEY"):
        return True, ""

    # Check for Coding Plan provider in modelProviders
    model_providers = data.get("modelProviders", {})
    if isinstance(model_providers, dict):
        openai_providers = model_providers.get("openai", [])
        if isinstance(openai_providers, list):
            coding_plan_endpoints = [
                "coding.dashscope.aliyuncs.com",
                "coding-intl.dashscope.aliyuncs.com",
            ]
            for provider in openai_providers:
                if isinstance(provider, dict):
                    base_url = provider.get("baseUrl", "")
                    if any(ep in str(base_url) for ep in coding_plan_endpoints):
                        return True, ""

    return False, "No Coding Plan configuration found"


def import_credentials(
    agent_home: Path,
    files: dict[str, str],
) -> dict[str, Any]:
    """
    Import uploaded credentials files.

    Args:
        agent_home: Agent home directory ($AGENT_HOME)
        files: Dict of filename -> content

    Returns:
        Import result with success/failure status
    """
    qwen_dir = agent_home / ".qwen"
    qwen_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, list[str]] = {
        "imported": [],
        "errors": [],
    }

    # Import oauth_creds.json
    if "oauth_creds.json" in files:
        content = files["oauth_creds.json"]
        valid, error = validate_oauth_creds(content)

        if not valid:
            result["errors"].append(f"oauth_creds.json: {error}")
        else:
            try:
                credentials_path = qwen_dir / "oauth_creds.json"
                with open(credentials_path, "w", encoding="utf-8") as f:
                    f.write(content)
                result["imported"].append("oauth_creds.json")
            except OSError as e:
                result["errors"].append(f"Failed to write oauth_creds.json: {e}")

    # Import settings.json
    if "settings.json" in files:
        content = files["settings.json"]
        valid, error = validate_settings_coding_plan(content)

        if not valid:
            result["errors"].append(f"settings.json: {error}")
        else:
            try:
                settings_path = qwen_dir / "settings.json"

                # Merge with existing settings
                if settings_path.exists():
                    try:
                        with open(settings_path, "r", encoding="utf-8") as f:
                            existing = json.load(f)
                    except (json.JSONDecodeError, OSError):
                        existing = {}
                else:
                    existing = {}

                new_data = json.loads(content)
                merged = _merge_settings(existing, new_data)

                with open(settings_path, "w", encoding="utf-8") as f:
                    json.dump(merged, f, indent=2)

                result["imported"].append("settings.json")
            except OSError as e:
                result["errors"].append(f"Failed to write settings.json: {e}")
            except json.JSONDecodeError as e:
                result["errors"].append(f"Invalid JSON in settings.json: {e}")

    return result


def _merge_settings(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """
    Merge new settings into existing settings.

    - modelProviders.openai[]: append or update by id
    - env: merge keys
    - security.auth: overwrite
    - model: overwrite
    """
    merged = dict(existing)

    # Merge modelProviders
    if "modelProviders" in new:
        if "modelProviders" not in merged:
            merged["modelProviders"] = {}

        for provider_type, providers in new["modelProviders"].items():
            if provider_type not in merged["modelProviders"]:
                merged["modelProviders"][provider_type] = []

            existing_providers = merged["modelProviders"][provider_type]
            existing_ids = {
                p.get("id") for p in existing_providers if isinstance(p, dict)
            }

            for new_provider in providers:
                if new_provider.get("id") not in existing_ids:
                    existing_providers.append(new_provider)
                else:
                    # Update existing provider
                    for i, p in enumerate(existing_providers):
                        if p.get("id") == new_provider.get("id"):
                            existing_providers[i] = new_provider
                            break

    # Merge env
    if "env" in new:
        if "env" not in merged:
            merged["env"] = {}
        merged["env"].update(new["env"])

    # Overwrite security.auth
    if "security" in new:
        if "security" not in merged:
            merged["security"] = {}
        if "auth" in new["security"]:
            merged["security"]["auth"] = new["security"]["auth"]

    # Overwrite model
    if "model" in new:
        merged["model"] = new["model"]

    return merged
