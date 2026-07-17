from __future__ import annotations

from pathlib import Path

from engine.intelligence.definition import IntelligenceDefinitionLoader
from engine.intelligence.history import IntelligenceHistoryWriter
from engine.intelligence.instance import IntelligenceInstance
from engine.intelligence.registry import AbilityRegistry, ToolRegistry
from engine.intelligence.router import IntelligenceRouter


class IntelligenceFactory:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.loader = IntelligenceDefinitionLoader()
        self.tool_registry = ToolRegistry()
        self.ability_registry = AbilityRegistry()
        self.history_writer = IntelligenceHistoryWriter(root=root)

    def create(self, definition_path: Path) -> IntelligenceInstance:
        definition = self.loader.load(definition_path)

        return IntelligenceInstance(
            definition=definition,
            data_engine=None,
            tool_registry=self.tool_registry,
            ability_registry=self.ability_registry,
            router=IntelligenceRouter(),
            history_writer=self.history_writer,
        )
