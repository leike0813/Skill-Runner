from __future__ import annotations

from pathlib import Path

from server.config import config

from . import keys


class ConfigRegistry:
    def __init__(self) -> None:
        self._root = Path(config.SYSTEM.ROOT).resolve()

    @property
    def root(self) -> Path:
        return self._root

    def engine_config_path(self, *, engine: str, filename: str) -> Path:
        return self.root / "server" / "engines" / engine / "config" / filename

    def contract_schema_path(self, filename: str) -> Path:
        return self.root / "server" / "contracts" / "schemas" / filename

    def contract_invariant_path(self, filename: str) -> Path:
        return self.root / "server" / "contracts" / "invariants" / filename

    def engine_command_profile_paths(self, engine: str) -> tuple[Path, ...]:
        return (self.engine_config_path(engine=engine, filename=keys.ENGINE_COMMAND_PROFILE_NAME),)

    def engine_auth_strategy_paths(self, engine: str) -> tuple[Path, ...]:
        return (self.engine_config_path(engine=engine, filename=keys.ENGINE_AUTH_STRATEGY_NAME),)

    def runtime_contract_schema_paths(self) -> tuple[Path, ...]:
        return (self.contract_schema_path(keys.RUNTIME_CONTRACT_SCHEMA_NAME),)

    def adapter_profile_schema_paths(self) -> tuple[Path, ...]:
        return (self.contract_schema_path(keys.ADAPTER_PROFILE_SCHEMA_NAME),)

    def engine_auth_strategy_schema_paths(self) -> tuple[Path, ...]:
        return (self.contract_schema_path(keys.ENGINE_AUTH_STRATEGY_SCHEMA_NAME),)

    def invariant_contract_paths(self, filename: str) -> tuple[Path, ...]:
        return (self.contract_invariant_path(filename),)

    def ask_user_schema_paths(self) -> tuple[Path, ...]:
        return (self.contract_schema_path(keys.ASK_USER_SCHEMA_NAME),)


config_registry = ConfigRegistry()
