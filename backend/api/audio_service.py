import os
import time
import json
import logging
import ffmpeg
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings
from transformers import pipeline
import torch

# Configure logger to use Django's logging setup
logger = logging.getLogger(__name__)

class AudioProcessingService:
    """
    An advanced service for video-to-audio processing, transcription, and quality analysis,
    integrated with Django settings.
    - Uses ffmpeg-python for robust audio extraction.
    - Integrates with Hugging Face transformers for local ASR.
    - Supports concurrent processing for improved performance.
    - Caches transcripts to avoid reprocessing.
    - Performs detailed, metric-based audio quality analysis.
    """
    def __init__(self, whisper_model: Optional[str] = None):
        # --- Integration with Django Settings ---
        config = settings.AUDIO_PROCESSING
        
        # Paths are resolved to be absolute, ensuring they work correctly from anywhere
        self.media_videos_path = Path(config.get("MEDIA_VIDEOS_PATH")).resolve()
        self.output_audio_path = Path(config.get("AUDIO_OUTPUT_PATH")).resolve()
        self.transcripts_path = self.output_audio_path / "transcripts"

        # Allow overriding Whisper model via management command argument
        self.model_id = whisper_model or config.get("WHISPER_MODEL", "openai/whisper-medium.en")
        
        # Set the device for computation (GPU if available, otherwise CPU)
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")

        # Initialize the Hugging Face ASR pipeline
        try:
            self.asr_pipeline = pipeline(
                "automatic-speech-recognition",
                model=self.model_id,
                device=self.device,
                # For word-level timestamps and avg_logprob, crucial for quality analysis
                return_timestamps="word",
                batch_size=16, # Adjust batch size for performance
            )
            logger.info(f"Successfully loaded Whisper pipeline with model: {self.model_id}")
        except Exception as e:
            logger.error(f"Failed to load Whisper pipeline: {e}")
            self.asr_pipeline = None

        # --- Configuration from your new script ---
        self.max_workers = 4 # Default concurrency

        # Create output directories if they don't exist
        self.output_audio_path.mkdir(parents=True, exist_ok=True)
        self.transcripts_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Video source path: {self.media_videos_path}")
        logger.info(f"Audio output path: {self.output_audio_path}")

    def _extract_audio(self, video_path: Path, audio_path: Path, force: bool = False) -> bool:
        """Extracts audio using ffmpeg-python. Returns True on success."""
        try:
            if audio_path.exists() and not force:
                logger.debug(f"Audio already exists, skipping extraction: {audio_path.name}")
                return True

            probe = ffmpeg.probe(str(video_path))
            has_audio = any(s['codec_type'] == 'audio' for s in probe['streams'])
            
            if not has_audio:
                logger.warning(f"Video file {video_path.name} does not contain an audio stream. Skipping.")
                return False

            (
                ffmpeg.input(str(video_path))
                .output(str(audio_path), acodec='pcm_s16le', ar=16000, ac=1, format='wav')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            logger.info(f"Successfully extracted audio: {audio_path.name}")
            return True
        except ffmpeg.Error as e:
            stderr = e.stderr.decode('utf-8') if e.stderr else 'No stderr'
            logger.error(f"FFmpeg error extracting {video_path.name}: {stderr}")
            return False
        except Exception:
            logger.exception(f"Unexpected error extracting audio from {video_path.name}")
            return False

    def _transcribe_audio(self, audio_path: Path) -> Dict:
        """Transcribes audio via Hugging Face pipeline."""
        if not self.asr_pipeline:
            return {'success': False, 'error': 'ASR pipeline not initialized'}

        if not audio_path.exists():
            return {'success': False, 'error': 'Audio file not found'}

        try:
            # The pipeline handles all pre-processing and model calls internally
            result = self.asr_pipeline(str(audio_path), generate_kwargs={"task": "transcribe"})
            
            # The pipeline returns a dictionary with 'text' and 'chunks' (if return_timestamps is set)
            transcription_result = self._parse_transcription_response(result)
            transcription_result['success'] = True
            return transcription_result
        except Exception:
            logger.exception(f"Unexpected error during transcription of {audio_path.name}")
            return {'success': False, 'error': 'Exception during transcription'}
        
    def _parse_transcription_response(self, body: dict) -> Dict:
        """Normalizes Hugging Face pipeline response into a standard dictionary."""
        # The pipeline output has 'text' and 'chunks'
        out = {
            'text': body.get('text', ''),
            'segments': body.get('chunks', []),
            'duration': None,
            'language': None, # The pipeline doesn't provide this by default, can be added with model call
            'raw': body
        }
        
        # Estimate duration from segments if available
        if out['segments']:
            try:
                # The pipeline's 'chunks' have a 'timestamp' key with [start, end]
                out['duration'] = max(seg.get('timestamp', [0, 0])[1] for seg in out['segments'])
            except (ValueError, TypeError):
                pass
        
        return out
        
    def _analyze_audio_quality(self, trans_result: Dict) -> Dict:
        """Performs a detailed quality analysis based on transcription metrics."""
        if not trans_result.get('success'):
            return {'quality_score': 0.0, 'analysis': 'Transcription failed.'}

        text = trans_result.get('text', '')
        segments = trans_result.get('segments', [])
        duration = trans_result.get('duration', 0.0)
        
        word_count = len(text.split())
        speech_duration = sum(seg.get('timestamp', [0,0])[1] - seg.get('timestamp', [0,0])[0] for seg in segments)
        silence_ratio = (duration - speech_duration) / duration if duration > 0 else 0
        wpm = (word_count / (speech_duration / 60)) if speech_duration > 0 else 0
        
        # Heuristic for confidence
        # Use 'avg_logprob' from pipeline chunks
        confidences = [seg.get('avg_logprob', -1) for seg in segments if 'avg_logprob' in seg]
        avg_confidence = (1 + (sum(confidences) / len(confidences) / 5.0)) if confidences else 0.5
        
        score = 0.0
        score += min(1.0, avg_confidence) * 40
        score += (1.0 - silence_ratio) * 20
        score += (10 if word_count > 20 else 3)
        
        if 120 <= wpm <= 180: score += 30
        elif 100 <= wpm < 120 or 180 < wpm <= 200: score += 20
        else: score += 10

        return {
            'quality_score': min(100.0, max(0.0, score)),
            'analysis': f"Score: {score:.1f}. WPM: {wpm:.1f}. Silence: {silence_ratio:.1%}. Confidence metric: {avg_confidence:.2f}",
        }

    def _process_one(self, video_file: Path) -> Dict:
        """Complete processing pipeline for a single video file."""
        result = {'video_file': str(video_file)}
        try:
            audio_file = self.output_audio_path / f"{video_file.stem}.wav"
            transcript_file = self.transcripts_path / f"{video_file.stem}.json"

            if not self._extract_audio(video_file, audio_file):
                return {**result, 'error': 'Audio extraction failed'}

            if transcript_file.exists():
                logger.info(f"Loading cached transcript for {video_file.name}")
                with transcript_file.open('r', encoding='utf-8') as f:
                    transcription_result = json.load(f)
            else:
                transcription_result = self._transcribe_audio(audio_file)
                if transcription_result.get('success'):
                    with transcript_file.open('w', encoding='utf-8') as f:
                        json.dump(transcription_result, f, indent=2)

            quality = self._analyze_audio_quality(transcription_result)
            
            return {
                **result,
                'audio_file': str(audio_file),
                'transcription': transcription_result.get('text', ''),
                'quality_analysis': quality
            }
        except Exception:
            logger.exception(f"Unhandled error processing {video_file.name}")
            return {**result, 'error': 'Unhandled exception in _process_one'}

    # --- Public methods for Django Command ---
    def process_single_video(self, video_filename: str) -> Dict:
        """Public method to process a single video by filename."""
        video_file = self.media_videos_path / video_filename
        if not video_file.exists():
            return {'error': f'Video not found: {video_file}'}
        return self._process_one(video_file)

    def process_all_videos(self) -> List[Dict]:
        """Public method to process all videos in the configured directory."""
        supported_formats = ('.mp4', '.mov', '.avi', '.mkv')
        video_files = [f for f in self.media_videos_path.iterdir() if f.suffix.lower() in supported_formats]
        
        if not video_files:
            logger.warning(f"No supported video files found in {self.media_videos_path}")
            return []

        logger.info(f"Processing {len(video_files)} files with concurrency={self.max_workers}")
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_video = {executor.submit(self._process_one, vf): vf for vf in video_files}
            for future in as_completed(future_to_video):
                res = future.result()
                results.append(res)
                video_name = os.path.basename(res.get('video_file', ''))
                score = res.get('quality_analysis', {}).get('quality_score', 'N/A')
                logger.info(f"Completed: {video_name} -> Quality Score: {score}")
        
        return results