"""
Configuration and resource loader.

Loads all YAML configurations from the config directory and
registers them with the system.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from memoir.core.registry import Registry, get_registry
from memoir.resources.question_bank import QuestionBank
from memoir.resources.prompt_template import PromptTemplate, GenerationPrompt
from memoir.resources.document_template import DocumentTemplate
from memoir.products.loader import ProductLoader


class ConfigLoader:
    """
    Loads configuration files and registers them with the system.
    
    This is the standard way to bootstrap the memoir platform with
    all its resources and product definitions.
    """
    
    def __init__(
        self,
        config_dir: Path | str | None = None,
        registry: Registry | None = None,
    ):
        self.registry = registry or get_registry()
        
        # Default to config/ directory relative to this file's parent
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / "config"
        self.config_dir = Path(config_dir)
    
    def load_all(self) -> dict[str, int]:
        """
        Load all configuration files.
        
        Returns:
            Dict with counts of each type loaded
        """
        counts = {
            "questions": 0,
            "prompts": 0,
            "templates": 0,
            "products": 0,
        }
        
        # Load question banks
        questions_dir = self.config_dir / "questions"
        if questions_dir.exists():
            for path in questions_dir.glob("*.yaml"):
                self.load_question_bank(path)
                counts["questions"] += 1
            for path in questions_dir.glob("*.yml"):
                self.load_question_bank(path)
                counts["questions"] += 1
        
        # Load prompt templates
        prompts_dir = self.config_dir / "prompts"
        if prompts_dir.exists():
            for path in prompts_dir.glob("*.yaml"):
                self.load_prompt_template(path)
                counts["prompts"] += 1
            for path in prompts_dir.glob("*.yml"):
                self.load_prompt_template(path)
                counts["prompts"] += 1
        
        # Load document templates
        templates_dir = self.config_dir / "templates"
        if templates_dir.exists():
            for path in templates_dir.glob("*.yaml"):
                self.load_document_template(path)
                counts["templates"] += 1
            for path in templates_dir.glob("*.yml"):
                self.load_document_template(path)
                counts["templates"] += 1
        
        # Load products (after resources so validation can work)
        products_dir = self.config_dir / "products"
        if products_dir.exists():
            loader = ProductLoader(self.registry)
            products = loader.load_directory(products_dir)
            counts["products"] = len(products)
        
        return counts
    
    def load_question_bank(self, path: Path | str) -> QuestionBank:
        """Load a question bank from YAML."""
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f)
        
        bank = QuestionBank.from_dict(data)
        self.registry.register_resource("questions", bank)
        return bank
    
    def load_prompt_template(self, path: Path | str) -> PromptTemplate:
        """Load a prompt template from YAML."""
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f)
        
        template = PromptTemplate.from_dict(data)
        self.registry.register_resource("prompts", template)
        return template
    
    def load_document_template(self, path: Path | str) -> DocumentTemplate:
        """Load a document template from YAML."""
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f)
        
        template = DocumentTemplate.from_dict(data)
        self.registry.register_resource("templates", template)
        return template


def load_config(config_dir: Path | str | None = None) -> dict[str, int]:
    """
    Convenience function to load all configuration.
    
    Returns:
        Dict with counts of each type loaded
    """
    loader = ConfigLoader(config_dir)
    return loader.load_all()

