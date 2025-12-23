"""
Prompt template resource.

Prompt templates define how AI services should generate content.
They include system prompts, generation prompts, and parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from memoir.resources.base import Resource


@dataclass
class GenerationPrompt:
    """A specific generation prompt within a template."""
    
    prompt: str
    parameters: dict[str, Any] = field(default_factory=dict)
    
    def interpolate(self, context: dict[str, Any]) -> str:
        """
        Interpolate variables in the prompt.
        
        Supports {subject.name}, {content}, etc.
        """
        text = self.prompt
        
        for key, value in context.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    text = text.replace(f"{{{key}.{subkey}}}", str(subvalue))
            elif isinstance(value, list):
                # For lists, join with newlines
                text = text.replace(f"{{{key}}}", "\n".join(str(v) for v in value))
            else:
                text = text.replace(f"{{{key}}}", str(value))
        
        return text
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "parameters": self.parameters,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenerationPrompt:
        return cls(
            prompt=data["prompt"],
            parameters=data.get("parameters", {}),
        )


class PromptTemplate(Resource):
    """
    A template for AI generation prompts.
    
    Prompt templates define the tone, style, and structure of
    AI-generated content. They can include multiple generation
    prompts for different purposes (memoir, summary, outline, etc.).
    """
    
    def __init__(
        self,
        resource_id: str,
        system_prompt: str,
        generation_prompts: dict[str, GenerationPrompt],
        name: str | None = None,
        description: str = "",
        tags: list[str] | None = None,
        version: int = 1,
        default_parameters: dict[str, Any] | None = None,
    ):
        self._resource_id = resource_id
        self._system_prompt = system_prompt
        self._generation_prompts = generation_prompts
        self._name = name or resource_id.replace("_", " ").title()
        self._description = description
        self._tags = tags or []
        self._version = version
        self._default_parameters = default_parameters or {
            "temperature": 0.7,
            "max_tokens": 2000,
        }
    
    @property
    def resource_id(self) -> str:
        return self._resource_id
    
    @property
    def resource_type(self) -> str:
        return "prompts"
    
    @property
    def version(self) -> int:
        return self._version
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def tags(self) -> list[str]:
        return self._tags
    
    @property
    def system_prompt(self) -> str:
        """The system prompt for AI context."""
        return self._system_prompt
    
    @property
    def default_parameters(self) -> dict[str, Any]:
        """Default parameters for generation."""
        return self._default_parameters
    
    def get_generation_prompt(self, prompt_type: str) -> GenerationPrompt | None:
        """Get a specific generation prompt by type."""
        return self._generation_prompts.get(prompt_type)
    
    def list_prompt_types(self) -> list[str]:
        """List available prompt types."""
        return list(self._generation_prompts.keys())
    
    def build_prompt(
        self,
        prompt_type: str,
        context: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        """
        Build a complete prompt for generation.
        
        Args:
            prompt_type: Type of prompt to use (e.g., "memoir", "summary")
            context: Variables to interpolate
            
        Returns:
            Tuple of (system_prompt, user_prompt, parameters)
        """
        gen_prompt = self._generation_prompts.get(prompt_type)
        if not gen_prompt:
            raise ValueError(f"Unknown prompt type: {prompt_type}")
        
        user_prompt = gen_prompt.interpolate(context)
        
        # Merge parameters: default < prompt-specific
        parameters = {**self._default_parameters, **gen_prompt.parameters}
        
        return self._system_prompt, user_prompt, parameters
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self._resource_id,
            "name": self._name,
            "description": self._description,
            "version": self._version,
            "tags": self._tags,
            "system_prompt": self._system_prompt,
            "default_parameters": self._default_parameters,
            "generation_prompts": {
                k: v.to_dict() for k, v in self._generation_prompts.items()
            },
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptTemplate:
        generation_prompts = {}
        for k, v in data.get("generation_prompts", {}).items():
            generation_prompts[k] = GenerationPrompt.from_dict(v)
        
        return cls(
            resource_id=data["id"],
            system_prompt=data["system_prompt"],
            generation_prompts=generation_prompts,
            name=data.get("name"),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            version=data.get("version", 1),
            default_parameters=data.get("default_parameters"),
        )

