"""
Enhanced Gemini Audio Analysis Service

This service processes audio files using Google's Gemini API for quality assessment
and content analysis, working alongside the video analysis service.
"""

import os
import logging
import json
import time
import base64
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

logger = logging.getLogger(__name__)


class GeminiAudioAnalysisService:
    """
    Service for analyzing audio files using Google's Gemini API
    
    Features:
    - Audio quality assessment
    - Content transcription and analysis
    - Speech clarity evaluation
    - Audio production quality scoring
    """
    
    def __init__(self):
        self.api_key = self._get_api_key()
        self.model_name = "gemini-2.5-flash"  # Best model for audio analysis
        self.client = None
        self.max_file_size_mb = 20  # 20MB limit for inline audio data
        
        if GEMINI_AVAILABLE and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.client = genai.GenerativeModel(self.model_name)
                logger.info("Gemini Audio Analysis Service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.client = None
        else:
            logger.warning("Gemini Audio Analysis Service not available - missing dependencies or API key")
    
    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment variables"""
        api_key = getattr(settings, 'GEMINI_API_KEY', None) or os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not api_key:
            logger.warning("No Gemini API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable")
        return api_key
    
    def is_available(self) -> bool:
        """Check if the service is available for use"""
        return GEMINI_AVAILABLE and self.client is not None and self.api_key is not None
    
    def _get_file_size_mb(self, file_path: str) -> float:
        """Get file size in MB"""
        try:
            size_bytes = os.path.getsize(file_path)
            return size_bytes / (1024 * 1024)
        except OSError:
            return 0
    
    def _prepare_audio_analysis_prompt(self) -> str:
        """Prepare the audio analysis prompt for balanced scoring"""
        return """
Please analyze this audio file and provide scores for key audio quality metrics. Be fair and realistic in your scoring - use the full 0-100 range but avoid being overly harsh. Most decent audio should score in the 40-80 range, with exceptional quality reaching 80-100.

**IMPORTANT: Please provide specific numerical scores for each category. Do not use default or identical scores.**

**AUDIO ANALYSIS AREAS:**

1. **AUDIO TECHNICAL QUALITY** (Score 0-100):
   - Overall audio clarity and fidelity
   - Absence of distortion, noise, or artifacts
   - Proper volume levels and dynamic range
   - Recording quality and equipment used
   - Well-recorded audio should score 60-90, poor quality 20-50
   **Score: [Provide specific number 0-100]**

2. **SPEECH CLARITY & INTELLIGIBILITY** (Score 0-100):
   - How clear and understandable is the speech?
   - Pronunciation, articulation, and diction quality
   - Absence of mumbling or unclear speech
   - Background noise interference with speech
   - Crystal clear speech should score 70-95, unclear speech 20-60
   **Score: [Provide specific number 0-100]**

3. **CONTENT ENGAGEMENT & DELIVERY** (Score 0-100):
   - How engaging is the speaker's delivery?
   - Energy, enthusiasm, and vocal variety
   - Pacing and rhythm appropriateness
   - Emotional expression and tone variation
   - Highly engaging delivery should score 60-90, monotone delivery 20-50
   **Score: [Provide specific number 0-100]**

4. **PRODUCTION VALUE** (Score 0-100):
   - Professional audio editing and mixing
   - Background music/sound effects balance
   - Audio transitions and flow
   - Overall polish and production quality
   - Professional production should score 50-85, basic recording 25-50
   **Score: [Provide specific number 0-100]**

5. **CONTENT APPROPRIATENESS** (Score 0-5):
   - Rate appropriateness (5 = completely appropriate, 0 = inappropriate)
   - Check for offensive language or inappropriate content
   - Cultural sensitivity and inclusivity
   - Most appropriate content should score 4-5
   **Score: [Provide specific number 0-5]**

**AUDIO TRANSCRIPTION & SUMMARY**:
Provide a brief transcription of key spoken content and a summary of what the audio contains.

**SCORING GUIDELINES:**
- Use realistic scoring: 0-30 (poor), 30-50 (below average), 50-70 (average), 70-85 (good), 85-100 (excellent)
- VARY your scores based on actual audio quality - avoid giving identical scores
- Consider the context and intended use of the audio
- Be fair but differentiate between different aspects of quality
- Most audio should fall in the 40-80 range with clear variation between categories

Please format your response as:
TECHNICAL QUALITY: [score]
SPEECH CLARITY: [score]
CONTENT ENGAGEMENT: [score]
PRODUCTION VALUE: [score]
APPROPRIATENESS: [score]

TRANSCRIPTION: [brief transcription of key content]
SUMMARY: [brief summary of audio content]
"""
    
    def analyze_audio(self, audio_path: str) -> Dict[str, Any]:
        """
        Analyze an audio file using Gemini API
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Dictionary containing analysis results
        """
        if not self.is_available():
            raise Exception("Gemini Audio Analysis Service is not available")
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        file_size_mb = self._get_file_size_mb(audio_path)
        logger.info(f"Analyzing audio: {audio_path} ({file_size_mb:.2f} MB)")
        
        try:
            # For now, handle as small file (can be extended for large files)
            return self._analyze_small_audio(audio_path)
                
        except Exception as e:
            logger.error(f"Error analyzing audio {audio_path}: {e}")
            raise
    
    def _analyze_small_audio(self, audio_path: str) -> Dict[str, Any]:
        """Analyze small audio files using inline data"""
        try:
            # Read audio data
            with open(audio_path, 'rb') as audio_file:
                audio_bytes = audio_file.read()
            
            # Import base64 for encoding
            import base64
            encoded_audio = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Create content parts for the API
            audio_part = {
                "inline_data": {
                    "mime_type": "audio/wav",
                    "data": encoded_audio
                }
            }
            
            text_part = {"text": self._prepare_audio_analysis_prompt()}
            
            # Generate content
            response = self.client.generate_content([audio_part, text_part])
            
            if response and response.text:
                return self._parse_audio_analysis_response(response.text, audio_path)
            else:
                raise Exception("Empty response from Gemini API")
                
        except Exception as e:
            logger.error(f"Error in small audio analysis: {e}")
            raise
    
    def _parse_audio_analysis_response(self, response_text: str, audio_path: str) -> Dict[str, Any]:
        """Parse the AI response and extract structured audio data"""
        try:
            # Initialize result structure
            result = {
                'success': True,
                'audio_path': audio_path,
                'analysis_timestamp': timezone.now().isoformat(),
                'raw_response': response_text,
                'technical_quality': 50,
                'speech_clarity': 50,
                'content_engagement': 50,
                'production_value': 50,
                'appropriateness': 5,
                'overall_score': 50,
                'transcription': '',
                'summary': ''
            }
            
            # Parse the response
            lines = response_text.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Parse scores
                if line.startswith('TECHNICAL QUALITY:'):
                    score = self._extract_score(line)
                    if score is not None:
                        result['technical_quality'] = max(0, min(100, score))
                elif line.startswith('SPEECH CLARITY:'):
                    score = self._extract_score(line)
                    if score is not None:
                        result['speech_clarity'] = max(0, min(100, score))
                elif line.startswith('CONTENT ENGAGEMENT:'):
                    score = self._extract_score(line)
                    if score is not None:
                        result['content_engagement'] = max(0, min(100, score))
                elif line.startswith('PRODUCTION VALUE:'):
                    score = self._extract_score(line)
                    if score is not None:
                        result['production_value'] = max(0, min(100, score))
                elif line.startswith('APPROPRIATENESS:'):
                    score = self._extract_score(line)
                    if score is not None:
                        result['appropriateness'] = max(0, min(5, score))
                elif line.startswith('TRANSCRIPTION:'):
                    result['transcription'] = line.replace('TRANSCRIPTION:', '').strip()
                elif line.startswith('SUMMARY:'):
                    result['summary'] = line.replace('SUMMARY:', '').strip()
            
            # Calculate overall audio quality score
            # Weights: Technical 40%, Speech Clarity 30%, Engagement 20%, Production 10%
            overall_score = (
                result['technical_quality'] * 0.40 +
                result['speech_clarity'] * 0.30 +
                result['content_engagement'] * 0.20 +
                result['production_value'] * 0.10
            )
            
            result['overall_score'] = round(overall_score, 1)
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing audio analysis response: {e}")
            # Return safe defaults on parsing error
            return {
                'success': False,
                'audio_path': audio_path,
                'analysis_timestamp': timezone.now().isoformat(),
                'error': str(e),
                'technical_quality': 50,
                'speech_clarity': 50,
                'content_engagement': 50,
                'production_value': 50,
                'appropriateness': 5,
                'overall_score': 50,
                'transcription': 'Unable to transcribe audio due to parsing error.',
                'summary': 'Audio analysis parsing failed.'
            }
    
    def _extract_score(self, line: str) -> Optional[float]:
        """Extract numerical score from a line of text"""
        import re
        
        # Look for patterns like "Score: 85", "85/100", "85", etc.
        patterns = [
            r'(\d+\.?\d*)/100',  # "85/100"
            r'(\d+\.?\d*)/5',    # "4/5" 
            r'Score:\s*(\d+\.?\d*)',  # "Score: 85"
            r':\s*(\d+\.?\d*)',  # ": 85"
            r'(\d+\.?\d*)',      # Just the number
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    score = float(match.group(1))
                    return score
                except (ValueError, IndexError):
                    continue
        
        return None

    def _extract_audio_from_video(self, video_path: str) -> Optional[str]:
        """
        Extract audio from video with multiple fallback methods.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Path to extracted audio file or None if failed
        """
        video_file = Path(video_path)
        temp_audio_path = video_file.parent / f"temp_{video_file.stem}_audio.wav"
        
        # Method 1: Try FFmpeg first (best quality)
        if self._extract_with_ffmpeg(video_path, str(temp_audio_path)):
            logger.info("Audio extracted successfully with FFmpeg")
            return str(temp_audio_path)
        
        # Method 2: Try ffmpeg-python
        if self._extract_with_ffmpeg_python(video_path, str(temp_audio_path)):
            logger.info("Audio extracted successfully with ffmpeg-python")
            return str(temp_audio_path)
        
        # Method 3: Try moviepy as fallback
        if self._extract_with_moviepy(video_path, str(temp_audio_path)):
            logger.info("Audio extracted successfully with moviepy")
            return str(temp_audio_path)
        
        logger.error("All audio extraction methods failed")
        return None
    
    def _extract_with_ffmpeg(self, video_path: str, audio_path: str) -> bool:
        """Extract audio using FFmpeg command line tool."""
        try:
            # Try to get FFmpeg from imageio_ffmpeg first
            ffmpeg_path = None
            try:
                import imageio_ffmpeg
                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
                logger.info(f"Using imageio_ffmpeg FFmpeg at: {ffmpeg_path}")
            except ImportError:
                logger.warning("imageio_ffmpeg not available, trying system FFmpeg")
            
            # Fallback to system FFmpeg if imageio_ffmpeg not available
            if not ffmpeg_path:
                import shutil
                ffmpeg_path = shutil.which('ffmpeg')
                if not ffmpeg_path:
                    logger.warning("FFmpeg not found in system PATH")
                    return False
                logger.info(f"Using system FFmpeg at: {ffmpeg_path}")
            
            cmd = [
                ffmpeg_path,
                '-i', video_path,
                '-vn',  # Disable video
                '-acodec', 'pcm_s16le',  # Audio codec
                '-ar', '16000',  # Sample rate
                '-ac', '1',  # Mono audio
                '-y',  # Overwrite output file
                audio_path
            ]
            
            logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=60  # 60 second timeout
            )
            
            if result.returncode == 0 and os.path.exists(audio_path):
                file_size = os.path.getsize(audio_path)
                logger.info(f"FFmpeg extraction successful: {audio_path} ({file_size} bytes)")
                return True
            else:
                logger.warning(f"FFmpeg failed with return code {result.returncode}")
                logger.warning(f"FFmpeg stderr: {result.stderr}")
                logger.warning(f"FFmpeg stdout: {result.stdout}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg extraction timed out")
            return False
        except Exception as e:
            logger.warning(f"FFmpeg extraction error: {e}")
            return False
    
    def _extract_with_ffmpeg_python(self, video_path: str, audio_path: str) -> bool:
        """Extract audio using ffmpeg-python library."""
        try:
            import ffmpeg
            
            stream = ffmpeg.input(video_path)
            audio = stream.audio
            out = ffmpeg.output(
                audio, 
                audio_path,
                acodec='pcm_s16le',
                ar=16000,
                ac=1,
                y=None  # Overwrite
            )
            ffmpeg.run(out, quiet=True, overwrite_output=True)
            
            if os.path.exists(audio_path):
                file_size = os.path.getsize(audio_path)
                logger.info(f"ffmpeg-python extraction successful: {audio_path} ({file_size} bytes)")
                return True
            return False
            
        except ImportError:
            logger.warning("ffmpeg-python library not available")
            return False
        except Exception as e:
            logger.warning(f"ffmpeg-python extraction error: {e}")
            return False
    
    def _extract_with_moviepy(self, video_path: str, audio_path: str) -> bool:
        """Extract audio using moviepy library."""
        try:
            from moviepy.editor import VideoFileClip
            
            video = VideoFileClip(video_path)
            audio = video.audio
            audio.write_audiofile(
                audio_path,
                codec='pcm_s16le',
                ffmpeg_params=['-ar', '16000', '-ac', '1'],
                verbose=False,
                logger=None
            )
            
            # Clean up
            audio.close()
            video.close()
            
            if os.path.exists(audio_path):
                file_size = os.path.getsize(audio_path)
                logger.info(f"moviepy extraction successful: {audio_path} ({file_size} bytes)")
                return True
            return False
            
        except ImportError:
            logger.warning("moviepy library not available")
            return False
        except Exception as e:
            logger.warning(f"moviepy extraction error: {e}")
            return False

    def analyze_video_audio(self, video_path: str) -> Dict[str, Any]:
        """
        Analyze audio from a video file by extracting it first with improved error handling.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dictionary containing audio analysis results
        """
        logger.info(f"Starting video audio analysis for: {video_path}")
        
        if not self.is_available():
            logger.error("Gemini Audio Analysis Service is not available")
            return {
                'success': False,
                'error': 'Gemini Audio Analysis Service is not available',
                'timestamp': timezone.now().isoformat()
            }
        
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return {
                'success': False,
                'error': f'Video file not found: {video_path}',
                'timestamp': timezone.now().isoformat()
            }
        
        # Extract audio from video
        temp_audio_path = self._extract_audio_from_video(video_path)
        
        if not temp_audio_path:
            logger.error("Failed to extract audio from video")
            return {
                'success': False,
                'error': 'Failed to extract audio from video. Please ensure FFmpeg is installed.',
                'timestamp': timezone.now().isoformat()
            }
        
        try:
            # Check if audio file was created and has content
            if not os.path.exists(temp_audio_path):
                logger.error("Audio file was not created")
                return {
                    'success': False,
                    'error': 'Audio extraction failed - no audio file created',
                    'timestamp': timezone.now().isoformat()
                }
            
            file_size = os.path.getsize(temp_audio_path)
            if file_size == 0:
                logger.error("Extracted audio file is empty")
                return {
                    'success': False,
                    'error': 'Extracted audio file is empty',
                    'timestamp': timezone.now().isoformat()
                }
            
            logger.info(f"Audio extracted successfully: {temp_audio_path} ({file_size} bytes)")
            
            # Analyze the extracted audio
            analysis_result = self.analyze_audio(temp_audio_path)
            
            # Add video-specific metadata
            analysis_result.update({
                'source_video': video_path,
                'extracted_audio_size': file_size,
                'extraction_method': 'ffmpeg',
                'video_to_audio_analysis': True
            })
            
            logger.info("Video audio analysis completed successfully")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error during video audio analysis: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Video audio analysis failed: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }
        
        finally:
            # Clean up temporary audio file
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                    logger.info(f"Cleaned up temporary audio file: {temp_audio_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary audio file {temp_audio_path}: {e}")


# Create a global instance
gemini_audio_service = GeminiAudioAnalysisService()
