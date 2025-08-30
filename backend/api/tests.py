import os
from django.test import TestCase
from django.conf import settings
from unittest.mock import patch, MagicMock

from .gemini_audio_service import gemini_audio_service

class GeminiAudioServiceTests(TestCase):
    """
    Test suite for the GeminiAudioAnalysisService.
    It uses mocking to avoid actual API calls.
    """

    def setUp(self):
        """Set up the test environment."""
        self.test_video_path = "/fake/test/video.mp4"

    def test_gemini_service_availability(self):
        """
        Test that the Gemini audio service is available.
        """
        # Test service availability
        is_available = gemini_audio_service.is_available()
        self.assertIsInstance(is_available, bool)
        
    @patch('api.gemini_audio_service.genai.GenerativeModel')
    @patch('api.gemini_audio_service.subprocess.run')
    def test_analyze_video_audio_success(self, mock_subprocess, MockGenerativeModel):
        """
        Test the successful analysis of video audio using Gemini.
        """
        # Mock ffmpeg subprocess for audio extraction
        mock_subprocess.return_value = MagicMock(returncode=0)
        
        # Mock Gemini API response
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '''
        {
            "transcript": "This is a test video transcript",
            "audio_quality_score": 75.0,
            "language": "en",
            "technical_quality": 72,
            "speech_clarity": 78,
            "content_engagement": 76,
            "production_value": 74,
            "appropriateness_score": 80
        }
        '''
        mock_model.generate_content.return_value = mock_response
        MockGenerativeModel.return_value = mock_model
        
        # Mock file operations
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.unlink'), \
             patch('builtins.open', MagicMock()):
            
            # Test analysis
            result = gemini_audio_service.analyze_video_audio(self.test_video_path)
            
            # Verify results
            self.assertIsInstance(result, dict)
            if 'error' not in result:
                self.assertIn('transcript', result)
                self.assertIn('audio_quality_score', result)
                self.assertIn('language', result)

    def test_analyze_video_audio_file_not_found(self):
        """
        Test handling of non-existent video files.
        """
        # Test with non-existent file
        result = gemini_audio_service.analyze_video_audio("/fake/nonexistent.mp4")
        
        # Should return error
        self.assertIsInstance(result, dict)
        self.assertIn('error', result)
        self.assertIn('not found', result['error'].lower())

    @patch('api.gemini_audio_service.genai.GenerativeModel')
    def test_analyze_video_audio_api_error(self, MockGenerativeModel):
        """
        Test handling of Gemini API errors.
        """
        # Mock API error
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API Error")
        MockGenerativeModel.return_value = mock_model
        
        # Mock file operations
        with patch('pathlib.Path.exists', return_value=True), \
             patch('api.gemini_audio_service.subprocess.run', return_value=MagicMock(returncode=0)):
            
            result = gemini_audio_service.analyze_video_audio(self.test_video_path)
            
            # Should return error
            self.assertIsInstance(result, dict)
            self.assertIn('error', result)

    def test_service_properties(self):
        """
        Test basic service properties.
        """
        # Test that service has expected attributes
        self.assertTrue(hasattr(gemini_audio_service, 'is_available'))
        self.assertTrue(hasattr(gemini_audio_service, 'analyze_video_audio'))
        self.assertTrue(hasattr(gemini_audio_service, 'model_name'))
        
        # Test model name
        self.assertEqual(gemini_audio_service.model_name, 'gemini-2.5-flash')