import os
from django.test import TestCase
from django.conf import settings
from unittest.mock import patch, MagicMock

from ..audio_service import AudioProcessingService

class AudioProcessingServiceTests(TestCase):
    """
    Test suite for the AudioProcessingService.
    It uses mocking to avoid actual file operations and API calls.
    """

    def setUp(self):
        """Set up the test environment."""
        # Define mock paths and settings for consistency
        self.mock_videos_path = "/tmp/mock_videos"
        self.mock_audio_path = "/tmp/mock_audio"
        os.makedirs(self.mock_videos_path, exist_ok=True)
        os.makedirs(self.mock_audio_path, exist_ok=True)

        # Create a dummy video file for path existence checks
        self.video_filename = "test_video.mp4"
        self.video_filepath = os.path.join(self.mock_videos_path, self.video_filename)
        with open(self.video_filepath, "w") as f:
            f.write("dummy video content")

        # Override Django settings for the duration of the test
        settings.AUDIO_PROCESSING = {
            "LMSTUDIO_BASE_URL": "http://localhost:1234/v1",
            "MEDIA_VIDEOS_PATH": self.mock_videos_path,
            "AUDIO_OUTPUT_PATH": self.mock_audio_path,
            "SAMPLE_RATE": 16000,
            "AUDIO_FORMAT": "wav",
        }
        self.service = AudioProcessingService()

    def tearDown(self):
        """Clean up after tests."""
        os.remove(self.video_filepath)
        os.rmdir(self.mock_videos_path)
        os.rmdir(self.mock_audio_path)

    @patch('api.audio_service.VideoFileClip')
    @patch('api.audio_service.OpenAI')
    def test_process_single_video_success(self, MockOpenAI, MockVideoFileClip):
        """
        Test the successful processing of a single video.
        """
        # --- Mock External Dependencies ---

        # 1. Mock moviepy's VideoFileClip for audio extraction
        mock_audio = MagicMock()
        mock_clip = MagicMock()
        mock_clip.audio = mock_audio
        MockVideoFileClip.return_value = mock_clip

        # 2. Mock the OpenAI client (for LMStudio)
        mock_openai_instance = MockOpenAI.return_value
        
        # Mock the transcription response
        mock_transcription = MagicMock()
        mock_transcription.text = "This is a test transcription."
        mock_openai_instance.audio.transcriptions.create.return_value = mock_transcription

        # Mock the chat completion (analysis) response
        mock_chat_response = MagicMock()
        mock_chat_response.choices[0].message.content = "Excellent clarity. Final score: 95/100."
        mock_openai_instance.chat.completions.create.return_value = mock_chat_response

        # --- Execute the Method ---
        result = self.service.process_single_video(self.video_filename)

        # --- Assert the Results ---
        self.assertNotIn("error", result)
        self.assertEqual(result["transcription"], "This is a test transcription.")
        self.assertEqual(result["quality_analysis"]["quality_score"], 95)
        self.assertIn("Excellent clarity", result["quality_analysis"]["summary"])

        # Verify that our mocks were called correctly
        MockVideoFileClip.assert_called_with(self.video_filepath)
        mock_openai_instance.audio.transcriptions.create.assert_called_once()
        mock_openai_instance.chat.completions.create.assert_called_once()

    def test_video_not_found(self):
        """
        Test the case where the video file does not exist.
        """
        result = self.service.process_single_video("non_existent_video.mp4")
        self.assertIn("error", result)
        self.assertIn("not found", result["error"])