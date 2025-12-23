"""
Voice Recorder Interface - Audio recording and transcription.

Uses OpenAI Whisper for transcription. Audio is stored in ContentStorage,
transcribed text becomes a ContentItem.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from typing import Any

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from memoir.core.events import Event
from memoir.core.models import ContentItem, ContentType
from memoir.interfaces.base import InputInterface, InputContext
from memoir.storage.base import StorageProvider


class VoiceRecorderInterface(InputInterface):
    """
    Interface for voice recording and transcription.
    
    Handles:
    - Audio file upload (wav, mp3, webm, etc.)
    - Transcription via OpenAI Whisper
    - Storage of both audio and transcript
    """
    
    _interface_id = "voice_recorder"
    
    @property
    def interface_id(self) -> str:
        return self._interface_id
    
    def __init__(
        self,
        storage: StorageProvider | None = None,
        openai_api_key: str | None = None,
    ):
        self.storage = storage
        self._openai_client: OpenAI | None = None
        self._api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
    
    @property
    def openai_client(self) -> OpenAI:
        """Lazy-load OpenAI client."""
        if self._openai_client is None:
            if not self._api_key:
                raise ValueError("OPENAI_API_KEY not set")
            self._openai_client = OpenAI(
                api_key=self._api_key,
                timeout=60.0,
            )
        return self._openai_client
    
    async def receive(
        self,
        raw_input: Any,
        context: InputContext,
    ) -> list[Event]:
        """
        Receive audio input and produce events.
        
        Args:
            raw_input: Audio bytes or dict with 'audio_data' and optional 'filename'
            context: Input context with project/contributor info
            
        Returns:
            List of events (content.created)
        """
        # Handle different input formats
        if isinstance(raw_input, dict):
            audio_data = raw_input.get("audio_data", raw_input.get("data"))
            filename = raw_input.get("filename", "recording.wav")
        else:
            audio_data = raw_input
            filename = "recording.wav"
        
        # Process the audio
        content_item = await self.process(
            audio_data=audio_data,
            project_id=context.project_id,
            contributor_id=context.contributor_id,
            question=context.question_text,
            question_id=context.question_id,
            filename=filename,
            **context.metadata,
        )
        
        # Return content.created event
        return [
            Event(
                event_type="content.created",
                project_id=context.project_id,
                payload={
                    "content_item": content_item.model_dump(),
                    "source_interface": self.interface_id,
                },
                contributor_id=context.contributor_id,
            )
        ]
    
    async def process(
        self,
        audio_data: bytes,
        project_id: str,
        contributor_id: str,
        question: str | None = None,
        question_id: str | None = None,
        filename: str = "recording.wav",
        **metadata: Any,
    ) -> ContentItem:
        """
        Process an audio recording: store, transcribe, create ContentItem.
        
        Args:
            audio_data: Raw audio bytes
            project_id: Project this belongs to
            contributor_id: Who recorded this
            question: The question being answered (optional)
            question_id: ID of the question (optional)
            filename: Original filename
            **metadata: Additional metadata
        
        Returns:
            ContentItem with transcript and audio reference
        """
        import uuid
        
        content_id = f"content_{uuid.uuid4().hex[:12]}"
        audio_key = f"{project_id}/{contributor_id}/{content_id}/{filename}"
        
        # Store audio file
        if self.storage:
            await self.storage.content.put(
                key=audio_key,
                data=audio_data,
                content_type=self._get_content_type(filename),
            )
        
        # Transcribe
        transcript = await self.transcribe(audio_data, filename)
        
        # Create content item
        content_item = ContentItem(
            id=content_id,
            project_id=project_id,
            contributor_id=contributor_id,
            content_type=ContentType.AUDIO,
            source_interface=self.interface_id,
            content={
                "question": question,
                "question_id": question_id,
                "answer_text": transcript["text"],
                "audio_key": audio_key if self.storage else None,
                "duration_seconds": transcript.get("duration"),
                "language": transcript.get("language", "en"),
            },
            source_metadata={
                "filename": filename,
                "transcription_model": "whisper-1",
                **metadata,
            },
            tags=self._extract_tags(question),
        )
        
        return content_item
    
    async def transcribe(
        self,
        audio_data: bytes,
        filename: str = "audio.wav",
    ) -> dict[str, Any]:
        """
        Transcribe audio data using OpenAI Whisper.
        
        Returns:
            Dict with 'text', 'language', optionally 'duration'
        """
        # Write to temp file (Whisper API needs a file)
        suffix = os.path.splitext(filename)[1] or ".wav"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(audio_data)
            temp_file.flush()
            temp_path = temp_file.name
        
        try:
            transcript = await self._transcribe_with_retry(temp_path)
            return {
                "text": transcript.text,
                "language": getattr(transcript, "language", "en"),
            }
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def _transcribe_with_retry(self, file_path: str):
        """Transcribe with retry logic."""
        def transcribe_sync():
            with open(file_path, "rb") as audio_file:
                return self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )
        
        # Run sync operation in thread pool with timeout
        return await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, transcribe_sync),
            timeout=90.0,
        )
    
    def _get_content_type(self, filename: str) -> str:
        """Get MIME type from filename."""
        ext = os.path.splitext(filename)[1].lower()
        return {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".webm": "audio/webm",
            ".m4a": "audio/mp4",
            ".ogg": "audio/ogg",
        }.get(ext, "audio/wav")
    
    def _extract_tags(self, question: str | None) -> list[str]:
        """Extract simple tags from question text."""
        if not question:
            return []
        
        question_lower = question.lower()
        tags = []
        
        tag_keywords = {
            "childhood": ["childhood", "child", "young", "kid", "grew up"],
            "family": ["family", "parent", "mother", "father", "sibling", "brother", "sister"],
            "education": ["school", "teacher", "learn", "class", "education"],
            "home": ["home", "house", "room", "neighborhood"],
            "friends": ["friend", "friendship", "play"],
            "memory": ["memory", "remember", "recall", "first"],
        }
        
        for tag, keywords in tag_keywords.items():
            if any(kw in question_lower for kw in keywords):
                tags.append(tag)
        
        return tags

