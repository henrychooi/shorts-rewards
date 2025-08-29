import os
import time
import json
import logging
import ffmpeg
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings
from transformers import pipeline
import torch

# Try to import moviepy as fallback
try:
    from moviepy.editor import VideoFileClip
    MOVIEPY_AVAILABLE = True
    MOVIEPY_ERROR = None
except ImportError as e:
    MOVIEPY_AVAILABLE = False
    VideoFileClip = None
    MOVIEPY_ERROR = f"Import failed: {e}"
except Exception as e:
    MOVIEPY_AVAILABLE = False
    VideoFileClip = None
    MOVIEPY_ERROR = f"Unexpected error: {e}"

def check_moviepy_availability():
    """Re-check MoviePy availability at runtime"""
    global MOVIEPY_AVAILABLE, VideoFileClip, MOVIEPY_ERROR
    try:
        import sys
        print(f"Python executable: {sys.executable}")
        print(f"Python path: {sys.path[:3]}...")  # Show first 3 paths
        
        # Try importing step by step
        import moviepy
        print(f"MoviePy base module found at: {moviepy.__file__}")
        
        # Check what's available in the moviepy package
        import os
        moviepy_dir = os.path.dirname(moviepy.__file__)
        print(f"MoviePy directory contents: {os.listdir(moviepy_dir)}")
        
        # Try importing editor specifically
        try:
            from moviepy.editor import VideoFileClip
            print("VideoFileClip imported successfully!")
            MOVIEPY_AVAILABLE = True
            MOVIEPY_ERROR = None
            return True
        except ImportError as editor_error:
            print(f"moviepy.editor import failed: {editor_error}")
            # Try alternative import
            try:
                from moviepy.video.io.VideoFileClip import VideoFileClip
                print("VideoFileClip imported via alternative path!")
                MOVIEPY_AVAILABLE = True
                MOVIEPY_ERROR = None
                return True
            except ImportError as alt_error:
                print(f"Alternative import also failed: {alt_error}")
                raise editor_error
        
    except ImportError as e:
        MOVIEPY_AVAILABLE = False
        VideoFileClip = None
        MOVIEPY_ERROR = f"Runtime import failed: {e}"
        print(f"MoviePy import error: {e}")
        return False
    except Exception as e:
        MOVIEPY_AVAILABLE = False
        VideoFileClip = None
        MOVIEPY_ERROR = f"Runtime unexpected error: {e}"
        print(f"MoviePy unexpected error: {e}")
        return False

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
        self.model_id = whisper_model or config.get("WHISPER_MODEL", "openai/whisper-tiny")
        self.hf_token = config.get("HF_TOKEN")  # Get Hugging Face token from config
        
        # Set the device for computation (GPU if available, otherwise CPU)
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")
        logger.info(f"HF Token available: {'Yes' if self.hf_token else 'No'}")

        # Initialize the ASR pipeline as None - will be loaded when first needed
        self.asr_pipeline = None
        self._pipeline_loaded = False
        self._pipeline_error = None

        # --- Configuration from your new script ---
        self.max_workers = 4 # Default concurrency

        # Create output directories if they don't exist
        self.output_audio_path.mkdir(parents=True, exist_ok=True)
        self.transcripts_path.mkdir(parents=True, exist_ok=True)
        
        # Check if FFmpeg is available
        self.ffmpeg_available = self._check_ffmpeg()
        
        # Re-check MoviePy availability at runtime (in case it was installed after Django started)
        if not MOVIEPY_AVAILABLE:
            check_moviepy_availability()
        
        if not self.ffmpeg_available:
            logger.warning("FFmpeg not found! Falling back to moviepy for audio extraction")
            if not MOVIEPY_AVAILABLE:
                logger.error("Neither FFmpeg nor moviepy available! Please install one of them")
                logger.error("FFmpeg: https://ffmpeg.org/download.html")
                logger.error("MoviePy: pip install moviepy")
        
        logger.info(f"Video source path: {self.media_videos_path}")
        logger.info(f"Audio output path: {self.output_audio_path}")
        logger.info(f"FFmpeg available: {self.ffmpeg_available}")
        logger.info(f"MoviePy available: {MOVIEPY_AVAILABLE}")
        if not MOVIEPY_AVAILABLE and MOVIEPY_ERROR:
            logger.warning(f"MoviePy error: {MOVIEPY_ERROR}")

    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available in the system PATH"""
        try:
            # Check if ffmpeg is in PATH
            if shutil.which('ffmpeg') is None:
                return False
            
            # Try to run ffmpeg -version to verify it works
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"FFmpeg check failed: {e}")
            return False

    def _load_pipeline_if_needed(self):
        """Lazy load the ASR pipeline when first needed"""
        if self._pipeline_loaded:
            return self.asr_pipeline is not None
        
        if self._pipeline_error:
            return False
            
        try:
            logger.info(f"Loading Whisper pipeline with model: {self.model_id}")
            
            # Build pipeline arguments with minimal parameters for compatibility
            pipeline_kwargs = {
                "model": self.model_id,
                "device": self.device,
                "return_timestamps": "word"
            }
            
            # Try to add token parameter if available
            try:
                self.asr_pipeline = pipeline(
                    "automatic-speech-recognition",
                    **pipeline_kwargs
                )
            except Exception as token_error:
                # Fallback without any token/auth parameters
                logger.warning(f"Failed with token, trying without: {token_error}")
                pipeline_kwargs = {
                    "model": self.model_id,
                    "device": self.device
                }
                self.asr_pipeline = pipeline(
                    "automatic-speech-recognition",
                    **pipeline_kwargs
                )
            
            self._pipeline_loaded = True
            logger.info(f"Successfully loaded Whisper pipeline")
            return True
        except Exception as e:
            logger.error(f"Failed to load Whisper pipeline: {e}")
            self._pipeline_error = str(e)
            self._pipeline_loaded = True
            self.asr_pipeline = None
            return False

    def _extract_audio(self, video_path: Path, audio_path: Path, force: bool = False) -> bool:
        """Extracts audio using ffmpeg-python or moviepy fallback. Returns True on success."""
        try:
            if audio_path.exists() and not force:
                logger.debug(f"Audio already exists, skipping extraction: {audio_path.name}")
                return True

            # Try FFmpeg first if available
            if self.ffmpeg_available:
                return self._extract_audio_ffmpeg(video_path, audio_path)
            # Fall back to moviepy
            elif MOVIEPY_AVAILABLE:
                return self._extract_audio_moviepy(video_path, audio_path)
            else:
                logger.error("No audio extraction method available (neither FFmpeg nor moviepy)")
                return False
                
        except Exception as e:
            logger.error(f"Unexpected error extracting audio from {video_path.name}")
            logger.exception(e)
            return False

    def _extract_audio_ffmpeg(self, video_path: Path, audio_path: Path) -> bool:
        """Extract audio using FFmpeg"""
        try:
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

    def _extract_audio_moviepy(self, video_path: Path, audio_path: Path) -> bool:
        """Extract audio using MoviePy as fallback"""
        try:
            logger.info(f"Using MoviePy to extract audio from {video_path.name}")
            
            # Load video and extract audio
            video = VideoFileClip(str(video_path))
            
            # Check if video has audio
            if video.audio is None:
                logger.warning(f"Video file {video_path.name} does not contain an audio stream. Skipping.")
                video.close()
                return False
            
            # Extract audio with the same parameters as FFmpeg
            audio = video.audio
            audio.write_audiofile(
                str(audio_path),
                codec='pcm_s16le',  # Same as FFmpeg
                ffmpeg_params=['-ar', '16000', '-ac', '1']  # 16kHz, mono
            )
            
            # Clean up
            audio.close()
            video.close()
            
            logger.info(f"Successfully extracted audio using MoviePy: {audio_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"MoviePy error extracting audio from {video_path.name}: {str(e)}")
            return False

    def _transcribe_audio(self, audio_path: Path) -> Dict:
        """Transcribes audio via Hugging Face pipeline."""
        if not self._load_pipeline_if_needed():
            return {'success': False, 'error': 'ASR pipeline not available'}

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
        
    def _analyze_audio_quality(self, trans_result: Dict, audio_path: Path = None) -> Dict:
        """
        Relaxed audio quality analysis prioritizing demographics, production quality, and viral content
        
        New Scoring System (100 points total):
        - Production Quality with Tone: 35 points (highest priority)
        - Demographic Appeal & Viral Content: 35 points (highest priority)
        - Speech Flow & Engagement: 20 points (baseline quality)
        - Bonus Multipliers: Up to 10 points for Gen Z viral content
        """
        if not trans_result.get('success'):
            # If transcription failed, try to analyze audio file directly for basic metrics
            if audio_path and audio_path.exists():
                return self._analyze_audio_file_direct(audio_path)
            else:
                return {
                    'quality_score': 0.0, 
                    'analysis': f'Transcription failed: {trans_result.get("error", "Unknown error")}'
                }

        text = trans_result.get('text', '').strip()
        segments = trans_result.get('segments', [])
        duration = trans_result.get('duration', 0.0)
        
        if not text or duration <= 0:
            return {
                'quality_score': 25.0,  # More generous base score
                'analysis': 'Limited audio content detected'
            }
        
        # RELAXED SCORING SYSTEM WITH PRIORITIES
        
        # 1. PRODUCTION QUALITY & TONE (35 points max - TOP PRIORITY)
        production_score = self._analyze_production_quality_relaxed(audio_path, segments, text, duration)
        
        # 2. DEMOGRAPHIC APPEAL & VIRAL CONTENT (35 points max - TOP PRIORITY)
        demographic_viral_score = self._analyze_demographic_viral_appeal(text)
        
        # 3. SPEECH FLOW & BASIC ENGAGEMENT (20 points max - BASELINE)
        flow_score = self._analyze_speech_flow_relaxed(segments, duration)
        
        # Base score calculation
        base_score = production_score + demographic_viral_score + flow_score
        
        # 4. GEN Z VIRAL BONUS (up to 10 points multiplier)
        viral_bonus = self._calculate_viral_bonus(text)
        
        total_score = min(100.0, base_score + viral_bonus)
        total_score = max(15.0, total_score)  # Minimum floor score
        
        # Generate detailed analysis
        word_count = len(text.split())
        speech_duration = sum(
            seg.get('timestamp', [0, 0])[1] - seg.get('timestamp', [0, 0])[0] 
            for seg in segments if seg.get('timestamp')
        )
        silence_ratio = ((duration - speech_duration) / duration * 100) if duration > 0 else 100
        
        analysis = (
            f"Total: {total_score:.1f}/100 | "
            f"Production: {production_score:.1f}/35 | "
            f"Demographics: {demographic_viral_score:.1f}/35 | "
            f"Flow: {flow_score:.1f}/20 | "
            f"Viral Bonus: {viral_bonus:.1f}/10"
        )
        
        return {
            'quality_score': total_score,
            'analysis': analysis,
            'breakdown': {
                'production_score': production_score,
                'demographic_viral_score': demographic_viral_score,
                'flow_score': flow_score,
                'viral_bonus': viral_bonus,
                'silence_percentage': silence_ratio,
                'word_count': word_count,
                'speech_duration': speech_duration
            }
        }
    
    def _analyze_production_quality_relaxed(self, audio_path: Path, segments: List, text: str, duration: float) -> float:
        """Relaxed production quality analysis with generous scoring (35 points max)"""
        if not segments:
            return 15.0  # More generous base score
            
        score = 0.0
        
        # AUDIO CLARITY FROM TRANSCRIPTION (15 points max - very generous)
        confidences = []
        for seg in segments:
            if 'avg_logprob' in seg:
                confidence = max(0, min(1, 1 + seg['avg_logprob'] / 5.0))
                confidences.append(confidence)
        
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            # More generous scoring curve
            if avg_confidence >= 0.3:  # Lower threshold
                score += 10 + (avg_confidence * 5)  # 10-15 points
            else:
                score += 5 + (avg_confidence * 10)  # 5-8 points
        else:
            score += 10.0  # Default generous score
        
        # SPEECH FLOW & CONSISTENCY (8 points max - generous)
        if len(segments) > 1:
            gaps = []
            for i in range(1, len(segments)):
                prev_end = segments[i-1].get('timestamp', [0, 0])[1]
                curr_start = segments[i].get('timestamp', [0, 0])[0]
                gap = curr_start - prev_end
                if gap > 0:
                    gaps.append(gap)
            
            if gaps:
                avg_gap = sum(gaps) / len(gaps)
                if avg_gap <= 1.0:  # Much more relaxed
                    score += 8.0
                elif avg_gap <= 2.0:
                    score += 6.0
                elif avg_gap <= 3.0:
                    score += 4.0
                else:
                    score += 2.0
            else:
                score += 7.0
        else:
            score += 6.0  # Single segment gets good score
        
        # ADVANCED TONE ANALYSIS (12 points max - enhanced weight)
        tone_score = self._analyze_audio_tone_relaxed(audio_path, text)
        score += tone_score
        
        return min(35.0, score)
    
    def _analyze_demographic_viral_appeal(self, text: str) -> float:
        """Combined demographic appeal and viral content analysis (35 points max)"""
        if not text:
            return 10.0  # Base score for having any content
            
        words = text.lower().split()
        score = 5.0  # Starting bonus
        
        # GEN Z VIRAL CONTENT (15 points max - HIGHEST PRIORITY)
        gen_z_viral_words = {
            'lowkey', 'highkey', 'deadass', 'bet', 'no cap', 'periodt', 'slay',
            'tea', 'spill', 'vibe', 'mood', 'energy', 'sus', 'based', 'cringe',
            'fr', 'facts', 'rizz', 'sigma', 'fire', 'lit', 'hits different',
            'say less', 'bestie', 'queen', 'king', 'iconic', 'legend', 'goat'
        }
        viral_count = sum(1 for word in words if word in gen_z_viral_words)
        # Very generous scoring for viral content
        score += min(15.0, viral_count * 3.0)
        
        # BROAD DEMOGRAPHIC APPEAL (10 points max)
        universal_appeal_words = {
            'amazing', 'awesome', 'incredible', 'fantastic', 'great', 'cool',
            'funny', 'hilarious', 'interesting', 'love', 'like', 'enjoy',
            'excited', 'happy', 'beautiful', 'perfect', 'best', 'favorite',
            'wonderful', 'brilliant', 'outstanding', 'excellent', 'nice'
        }
        appeal_count = sum(1 for word in words if word in universal_appeal_words)
        score += min(10.0, appeal_count * 1.5)
        
        # ENGAGEMENT INDICATORS (10 points max)
        engagement_words = {
            'wow', 'omg', 'whoa', 'damn', 'dude', 'guys', 'everyone',
            'check', 'look', 'see', 'watch', 'listen', 'hear', 'feel',
            'think', 'know', 'get', 'understand', 'remember', 'imagine'
        }
        engagement_count = sum(1 for word in words if word in engagement_words)
        score += min(10.0, engagement_count * 1.2)
        
        # BONUS FOR LONGER CONTENT (5 points max)
        word_count = len(words)
        if word_count >= 20:
            score += 5.0
        elif word_count >= 10:
            score += 3.0
        elif word_count >= 5:
            score += 2.0
        
        return min(35.0, score)
    
    def _analyze_speech_flow_relaxed(self, segments: List, duration: float) -> float:
        """Relaxed speech flow analysis focusing on basic quality (20 points max)"""
        if not segments or duration <= 0:
            return 8.0  # Generous base score
            
        speech_duration = sum(
            seg.get('timestamp', [0, 0])[1] - seg.get('timestamp', [0, 0])[0] 
            for seg in segments if seg.get('timestamp')
        )
        
        silence_ratio = (duration - speech_duration) / duration
        
        # Much more relaxed silence scoring
        if silence_ratio <= 0.2:  # 20% or less silence - excellent
            return 20.0
        elif silence_ratio <= 0.4:  # 20-40% silence - very good
            return 18.0
        elif silence_ratio <= 0.6:  # 40-60% silence - good
            return 15.0
        elif silence_ratio <= 0.8:  # 60-80% silence - okay
            return 12.0
        else:  # >80% silence - still gets points
            return 8.0
    
    def _calculate_viral_bonus(self, text: str) -> float:
        """Calculate bonus points for viral Gen Z content (10 points max)"""
        if not text:
            return 0.0
            
        words = text.lower().split()
        text_lower = text.lower()
        
        bonus = 0.0
        
        # TRENDING SLANG BONUS (5 points max)
        trending_words = {
            'rizz', 'sigma', 'ohio', 'skibidi', 'gyat', 'bussin', 'sheesh',
            'cap', 'no cap', 'periodt', 'slay', 'hits different', 'say less'
        }
        trending_phrases = ['no cap', 'hits different', 'say less', 'periodt']
        
        trending_count = sum(1 for word in words if word in trending_words)
        phrase_count = sum(1 for phrase in trending_phrases if phrase in text_lower)
        bonus += min(5.0, (trending_count + phrase_count * 2) * 1.0)
        
        # VIRAL ENERGY BONUS (3 points max)
        energy_indicators = text.count('!') + text.count('?') + text.count('OMG') + text.count('omg')
        bonus += min(3.0, energy_indicators * 0.5)
        
        # LENGTH & COMPLEXITY BONUS (2 points max)
        if len(words) >= 15 and any(word in trending_words for word in words):
            bonus += 2.0
        elif len(words) >= 8 and any(word in trending_words for word in words):
            bonus += 1.0
        
        return min(10.0, bonus)
    
    def _analyze_audio_tone_relaxed(self, audio_path: Path, text: str) -> float:
        """Relaxed tone analysis with generous scoring (12 points max)"""
        try:
            import librosa
            import numpy as np
            
            if not audio_path or not audio_path.exists():
                return self._analyze_tone_from_text_relaxed(text)
            
            # Load audio file
            y, sr = librosa.load(str(audio_path), sr=None)
            
            if len(y) == 0:
                return self._analyze_tone_from_text_relaxed(text)
            
            tone_score = 2.0  # Base tone score
            
            # 1. ENERGY & DYNAMICS (5 points max - generous)
            rms = librosa.feature.rms(y=y)[0]
            rms_mean = np.mean(rms)
            rms_std = np.std(rms)
            
            # Much more generous energy scoring
            energy_score = min(5.0, 2 + (rms_mean * 15 + rms_std * 10))
            tone_score += energy_score
            
            # 2. PITCH VARIATION (3 points max - generous)
            pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
            pitch_values = []
            
            for t in range(pitches.shape[1]):
                index = magnitudes[:, t].argmax()
                pitch = pitches[index, t]
                if pitch > 0:
                    pitch_values.append(pitch)
            
            if pitch_values:
                pitch_std = np.std(pitch_values)
                pitch_score = min(3.0, 1 + (pitch_std / 30.0))  # More generous
                tone_score += pitch_score
            else:
                tone_score += 2.0  # Default good score
            
            # 3. SPECTRAL QUALITY (2 points max - very generous)
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            centroid_mean = np.mean(spectral_centroids)
            
            # Much wider optimal range
            if 500 <= centroid_mean <= 5000:  # Very broad range
                tone_score += 2.0
            elif 300 <= centroid_mean <= 6000:
                tone_score += 1.5
            else:
                tone_score += 1.0
            
            return min(12.0, tone_score)
            
        except ImportError:
            return self._analyze_tone_from_text_relaxed(text)
        except Exception as e:
            logger.warning(f"Audio tone analysis failed: {e}")
            return self._analyze_tone_from_text_relaxed(text)
    
    def _analyze_tone_from_text_relaxed(self, text: str) -> float:
        """Relaxed text-based tone analysis (12 points max)"""
        if not text:
            return 4.0  # Base score
        
        words = text.lower().split()
        score = 4.0  # Starting bonus
        
        # EMOTIONAL INTENSITY (5 points max - generous)
        high_energy_words = {
            'amazing', 'incredible', 'awesome', 'fantastic', 'excited', 'thrilled',
            'love', 'hate', 'obsessed', 'crazy', 'insane', 'unbelievable',
            'wow', 'omg', 'brilliant', 'stunning', 'gorgeous', 'beautiful',
            'fire', 'lit', 'sick', 'dope', 'epic', 'legendary'
        }
        energy_count = sum(1 for word in words if word in high_energy_words)
        score += min(5.0, energy_count * 1.5)  # More generous
        
        # EXPRESSIVENESS (3 points max - generous)
        punctuation_score = min(3.0, (text.count('!') + text.count('?')) * 0.8)
        score += punctuation_score
        
        # VOCAL VARIETY (4 points max - generous)
        variety_words = {
            'really', 'very', 'so', 'super', 'totally', 'absolutely',
            'definitely', 'actually', 'literally', 'honestly', 'seriously',
            'completely', 'extremely', 'incredibly', 'amazingly'
        }
        variety_count = sum(1 for word in words if word in variety_words)
        score += min(4.0, variety_count * 0.8)
        
        return min(12.0, score)
        """Enhanced silence scoring that considers natural pauses and speech rhythm"""
        if not segments or duration <= 0:
            return 0.0
            
        speech_duration = sum(
            seg.get('timestamp', [0, 0])[1] - seg.get('timestamp', [0, 0])[0] 
            for seg in segments if seg.get('timestamp')
        )
        
        silence_ratio = (duration - speech_duration) / duration
        
        # More nuanced scoring - some silence can be good for dramatic effect
        if silence_ratio <= 0.05:  # Very little silence - might be rushed
            return 15.0
        elif silence_ratio <= 0.15:  # Optimal range - natural speech
            return 20.0
        elif silence_ratio <= 0.25:  # Good range - allows for emphasis
            return 18.0
        elif silence_ratio <= 0.35:  # Acceptable - might be storytelling style
            return 14.0
        elif silence_ratio <= 0.50:  # Moderate - could be contemplative content
            return 10.0
        elif silence_ratio <= 0.65:  # High silence - better have good reason
            return 6.0
        else:  # Too much silence unless it's artistic
            return 2.0

    def _analyze_content_viral_potential(self, text: str) -> float:
        """Analyze content for viral potential and engagement factors"""
        if not text:
            return 0.0
            
        words = text.lower().split()
        word_count = len(words)
        
        score = 5.0  # Base score
        
        # VIRAL TRIGGERS (8 points max)
        viral_keywords = {
            'wow', 'omg', 'insane', 'crazy', 'unbelievable', 'shocking', 'viral',
            'trending', 'epic', 'legendary', 'iconic', 'fire', 'slaps', 'hits different',
            'no cap', 'facts', 'periodt', 'slay', 'queen', 'king', 'boss', 'savage'
        }
        viral_count = sum(1 for word in words if word in viral_keywords)
        score += min(8.0, viral_count * 2)
        
        # EMOTIONAL INTENSITY (7 points max)
        high_emotion_words = {
            'love', 'hate', 'amazing', 'terrible', 'incredible', 'awful', 'fantastic',
            'horrible', 'perfect', 'disaster', 'brilliant', 'stupid', 'genius', 'idiot',
            'obsessed', 'addicted', 'crying', 'screaming', 'dying', 'killing', 'slaying'
        }
        emotion_count = sum(1 for word in words if word in high_emotion_words)
        score += min(7.0, emotion_count * 1.5)
        
        # CALL TO ACTION & ENGAGEMENT (5 points max)
        engagement_phrases = {
            'comment', 'like', 'subscribe', 'follow', 'share', 'tell me', 'what do you think',
            'let me know', 'thoughts', 'opinion', 'agree', 'disagree', 'vote', 'choose',
            'pick', 'decide', 'help', 'advice'
        }
        engagement_count = sum(1 for word in words if word in engagement_phrases)
        score += min(5.0, engagement_count * 1.2)
        
        # CONTENT LENGTH OPTIMIZATION (5 points max)
        if 15 <= word_count <= 50:  # Sweet spot for short content
            score += 5.0
        elif 10 <= word_count < 15 or 50 < word_count <= 80:
            score += 3.0
        elif 5 <= word_count < 10 or 80 < word_count <= 120:
            score += 1.0
        
        # STORYTELLING ELEMENTS (5 points max)
        story_words = {
            'so', 'then', 'suddenly', 'meanwhile', 'first', 'next', 'finally',
            'story', 'happened', 'remember', 'once', 'time', 'day', 'moment'
        }
        story_count = sum(1 for word in words if word in story_words)
        score += min(5.0, story_count * 1)
        
        return min(30.0, score)

    def _analyze_demographic_appeal_enhanced(self, text: str) -> float:
        """Enhanced analysis of appeal across different age groups and demographics (25 points max)"""
        if not text:
            return 0.0
            
        words = text.lower().split()
        score = 0.0
        
        # GEN Z APPEAL (8 points max - increased)
        gen_z_words = {
            'lowkey', 'highkey', 'deadass', 'bet', 'no cap', 'periodt', 'slay',
            'tea', 'spill', 'vibe', 'mood', 'energy', 'sus', 'based', 'cringe',
            'toxic', 'main character', 'npc', 'rizz', 'sigma', 'fr', 'facts'
        }
        gen_z_count = sum(1 for word in words if word in gen_z_words)
        score += min(8.0, gen_z_count * 1.0)
        
        # MILLENNIAL APPEAL (6 points max - increased)
        millennial_words = {
            'adulting', 'goals', 'squad', 'bae', 'lit', 'fire', 'savage', 'queen',
            'king', 'boss', 'salty', 'shade', 'thirsty', 'extra', 'basic', 'iconic',
            'legendary', 'epic', 'amazing', 'incredible'
        }
        millennial_count = sum(1 for word in words if word in millennial_words)
        score += min(6.0, millennial_count * 0.8)
        
        # UNIVERSAL APPEAL (6 points max - increased)
        universal_words = {
            'funny', 'hilarious', 'interesting', 'cool', 'awesome', 'amazing',
            'incredible', 'fantastic', 'great', 'good', 'nice', 'beautiful',
            'happy', 'excited', 'love', 'enjoy', 'favorite', 'best', 'wonderful',
            'perfect', 'excellent', 'brilliant', 'outstanding'
        }
        universal_count = sum(1 for word in words if word in universal_words)
        score += min(6.0, universal_count * 0.4)
        
        # ACCESSIBILITY & CLARITY (5 points max - increased)
        # Clear, simple language that's easy to understand
        simple_ratio = sum(1 for word in words if len(word) <= 6) / len(words) if words else 0
        if simple_ratio >= 0.8:  # 80% simple words
            score += 5.0
        elif simple_ratio >= 0.7:
            score += 4.0
        elif simple_ratio >= 0.6:
            score += 3.0
        elif simple_ratio >= 0.5:
            score += 2.0
        elif simple_ratio >= 0.4:
            score += 1.0
        
        return min(25.0, score)

    def _analyze_production_quality_enhanced(self, audio_path: Path, segments: List, text: str, duration: float) -> float:
        """Enhanced production quality analysis with tone analysis (25 points max)"""
        if not segments:
            return 0.0
            
        score = 0.0
        
        # AUDIO CLARITY FROM TRANSCRIPTION (8 points max)
        confidences = []
        for seg in segments:
            if 'avg_logprob' in seg:
                confidence = max(0, min(1, 1 + seg['avg_logprob'] / 5.0))
                confidences.append(confidence)
        
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            score += avg_confidence * 8.0
        else:
            score += 4.0  # Default moderate score
        
        # SPEECH CONSISTENCY & FLOW (5 points max)
        if len(segments) > 1:
            gaps = []
            for i in range(1, len(segments)):
                prev_end = segments[i-1].get('timestamp', [0, 0])[1]
                curr_start = segments[i].get('timestamp', [0, 0])[0]
                gap = curr_start - prev_end
                if gap > 0:
                    gaps.append(gap)
            
            if gaps:
                avg_gap = sum(gaps) / len(gaps)
                if avg_gap <= 0.3:
                    score += 5.0
                elif avg_gap <= 0.8:
                    score += 4.0
                elif avg_gap <= 1.5:
                    score += 2.0
                else:
                    score += 1.0
            else:
                score += 4.0
        
        # CONTENT DENSITY & PACING (4 points max)
        if duration > 0:
            word_density = len(text.split()) / duration
            if 1.5 <= word_density <= 4.0:  # Good information density
                score += 4.0
            elif 1.0 <= word_density < 1.5 or 4.0 < word_density <= 5.0:
                score += 3.0
            elif 0.5 <= word_density < 1.0 or 5.0 < word_density <= 6.0:
                score += 2.0
            else:
                score += 1.0
        
        # ADVANCED TONE ANALYSIS (8 points max)
        tone_score = self._analyze_audio_tone(audio_path, text)
        score += tone_score
        
        return min(25.0, score)
    
    def _analyze_audio_tone(self, audio_path: Path, text: str) -> float:
        """Analyze audio tone characteristics using librosa (8 points max)"""
        try:
            import librosa
            import numpy as np
            
            if not audio_path or not audio_path.exists():
                # Fallback to text-based tone analysis
                return self._analyze_tone_from_text(text)
            
            # Load audio file
            y, sr = librosa.load(str(audio_path), sr=None)
            
            if len(y) == 0:
                return self._analyze_tone_from_text(text)
            
            tone_score = 0.0
            
            # 1. ENERGY & DYNAMICS (3 points max)
            # RMS energy analysis
            rms = librosa.feature.rms(y=y)[0]
            rms_mean = np.mean(rms)
            rms_std = np.std(rms)
            
            # Higher energy and variation indicates more engaging audio
            energy_score = min(3.0, (rms_mean * 10 + rms_std * 5))
            tone_score += energy_score
            
            # 2. PITCH VARIATION & EXPRESSIVENESS (3 points max)
            # Extract pitch using librosa
            pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
            pitch_values = []
            
            for t in range(pitches.shape[1]):
                index = magnitudes[:, t].argmax()
                pitch = pitches[index, t]
                if pitch > 0:  # Valid pitch
                    pitch_values.append(pitch)
            
            if pitch_values:
                pitch_std = np.std(pitch_values)
                # More pitch variation indicates more expressive speech
                pitch_score = min(3.0, pitch_std / 50.0)  # Normalize pitch variation
                tone_score += pitch_score
            else:
                tone_score += 1.0  # Default if no pitch detected
            
            # 3. SPECTRAL QUALITY (2 points max)
            # Spectral centroid - indicates brightness/clarity
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            centroid_mean = np.mean(spectral_centroids)
            
            # Optimal range for speech clarity (around 1000-3000 Hz)
            if 1000 <= centroid_mean <= 3000:
                tone_score += 2.0
            elif 800 <= centroid_mean < 1000 or 3000 < centroid_mean <= 4000:
                tone_score += 1.5
            elif 600 <= centroid_mean < 800 or 4000 < centroid_mean <= 5000:
                tone_score += 1.0
            else:
                tone_score += 0.5
            
            return min(8.0, tone_score)
            
        except ImportError:
            # Librosa not available, fallback to text analysis
            return self._analyze_tone_from_text(text)
        except Exception as e:
            logger.warning(f"Audio tone analysis failed: {e}")
            return self._analyze_tone_from_text(text)
    
    def _analyze_tone_from_text(self, text: str) -> float:
        """Fallback tone analysis based on text content (8 points max)"""
        if not text:
            return 0.0
        
        words = text.lower().split()
        score = 0.0
        
        # EMOTIONAL INTENSITY (4 points max)
        high_energy_words = {
            'amazing', 'incredible', 'awesome', 'fantastic', 'excited', 'thrilled',
            'love', 'hate', 'obsessed', 'crazy', 'insane', 'unbelievable',
            'wow', 'omg', 'brilliant', 'stunning', 'gorgeous', 'beautiful'
        }
        energy_count = sum(1 for word in words if word in high_energy_words)
        score += min(4.0, energy_count * 0.8)
        
        # EXPRESSIVENESS INDICATORS (2 points max)
        # Exclamation marks and question marks indicate vocal variation
        punctuation_score = min(2.0, (text.count('!') + text.count('?')) * 0.5)
        score += punctuation_score
        
        # VOCAL VARIETY INDICATORS (2 points max)
        variety_words = {
            'really', 'very', 'so', 'super', 'totally', 'absolutely',
            'definitely', 'actually', 'literally', 'honestly'
        }
        variety_count = sum(1 for word in words if word in variety_words)
        score += min(2.0, variety_count * 0.4)
        
        return min(8.0, score)
    
    def _analyze_audio_file_direct(self, audio_path: Path) -> Dict:
        """Direct audio file analysis when transcription fails"""
        try:
            import librosa
            import numpy as np
            
            # Load audio file
            y, sr = librosa.load(str(audio_path), sr=16000)
            duration = len(y) / sr
            
            # Calculate silence percentage
            # Use RMS energy to detect silence
            hop_length = 512
            frame_length = 2048
            rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
            
            # Threshold for silence (adjust as needed)
            silence_threshold = np.percentile(rms, 20)  # Bottom 20% considered silence
            silence_frames = np.sum(rms < silence_threshold)
            total_frames = len(rms)
            silence_ratio = silence_frames / total_frames if total_frames > 0 else 1.0
            
            # Basic scoring based on silence and duration
            score = 10.0  # Base score for having audio
            
            # Silence scoring (20 points)
            if silence_ratio <= 0.3:
                score += 20.0
            elif silence_ratio <= 0.5:
                score += 15.0
            elif silence_ratio <= 0.7:
                score += 10.0
            else:
                score += 5.0
            
            # Duration scoring (10 points)
            if duration >= 10:
                score += 10.0
            elif duration >= 5:
                score += 7.0
            elif duration >= 2:
                score += 4.0
            
            return {
                'quality_score': min(50.0, score),  # Max 50 without transcription
                'analysis': f'Direct audio analysis - {silence_ratio*100:.1f}% silence, {duration:.1f}s duration (transcription unavailable)'
            }
            
        except ImportError:
            # librosa not available, return basic score
            return {
                'quality_score': 25.0,
                'analysis': 'Basic audio analysis (advanced audio processing unavailable)'
            }
        except Exception as e:
            return {
                'quality_score': 10.0,
                'analysis': f'Audio analysis failed: {str(e)}'
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

            quality = self._analyze_audio_quality(transcription_result, audio_file)
            
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