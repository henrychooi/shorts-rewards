"""
Enhanced Gemini Audio Analysis Service

This service processes audio files using Google's Gemini API for quality assessment
and content analysis, working alongside the video analysis service.
"""

import os
import logging
import json
import time
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

    def analyze_video_audio(self, video_path: str) -> Dict[str, Any]:
        """
        Analyze audio from a video file by extracting it first
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dictionary containing audio analysis results
        """
        if not self.is_available():
            return {'error': 'Gemini Audio Analysis Service is not available'}
        
        if not os.path.exists(video_path):
            return {'error': f'Video file not found: {video_path}'}
        
        # Extract audio from video using ffmpeg
        temp_audio_path = None
        try:
            # Create temporary audio file path
            video_file = Path(video_path)
            temp_audio_path = video_file.parent / f"temp_{video_file.stem}_audio.wav"
            
            # Use ffmpeg to extract audio
            import subprocess
            
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-vn',  # Disable video
                '-acodec', 'pcm_s16le',  # Audio codec
                '-ar', '16000',  # Sample rate
                '-ac', '1',  # Mono audio
                '-y',  # Overwrite output file
                str(temp_audio_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg failed: {result.stderr}")
                return {'error': f'Failed to extract audio from video: {result.stderr}'}
            
            if not temp_audio_path.exists():
                return {'error': 'Audio extraction failed - no audio file created'}
            
            # Analyze the extracted audio
            analysis_result = self.analyze_audio(str(temp_audio_path))
            
            # Add video file info to the result
            analysis_result['source_video'] = str(video_path)
            analysis_result['audio_quality_score'] = analysis_result.get('overall_score', 50)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing video audio {video_path}: {e}")
            return {'error': f'Video audio analysis failed: {str(e)}'}
        
        finally:
            # Clean up temporary audio file
            if temp_audio_path and temp_audio_path.exists():
                try:
                    temp_audio_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temporary audio file {temp_audio_path}: {e}")


# Create a global instance
gemini_audio_service = GeminiAudioAnalysisService()
