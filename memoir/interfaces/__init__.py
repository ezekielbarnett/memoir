"""Interfaces - adapters for content to enter and exit the system."""

from memoir.interfaces.base import InputInterface, OutputInterface, ExportResult
from memoir.interfaces.input import VoiceRecorderInterface, WebFormInterface

__all__ = [
    "InputInterface",
    "OutputInterface",
    "ExportResult",
    "VoiceRecorderInterface",
    "WebFormInterface",
]

