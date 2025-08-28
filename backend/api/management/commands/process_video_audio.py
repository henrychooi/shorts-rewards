import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import json
from api.audio_service import AudioProcessingService # Corrected import path

class Command(BaseCommand):
    help = 'Process video files to extract and analyze audio quality using Whisper'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--video',
            type=str,
            help='Process a specific video file (filename only)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all video files in the media directory',
        )
        parser.add_argument(
            '--report',
            action='store_true',
            help='Generate a quality report only (no processing)',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path for results (JSON format)',
        )
        parser.add_argument(
        '--whisper-model',
        type=str,
        default='openai/whisper-medium.en', 
        help='Hugging Face Whisper model ID (default: openai/whisper-medium.en)',
    )
    
    def handle(self, *args, **options):
        try:
            # Initialize audio service
            audio_service = AudioProcessingService(
                whisper_model=options['whisper_model']
            )
            
            results = []
            
            if options['video']:
                # Process single video
                self.stdout.write(f"Processing single video: {options['video']}")
                result = audio_service.process_single_video(options['video'])
                results = [result]
                
                if 'error' in result:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing {options['video']}: {result['error']}")
                    )
                else:
                    quality_score = result.get('quality_analysis', {}).get('quality_score', 0)
                    self.stdout.write(
                        self.style.SUCCESS(f"Successfully processed {options['video']} - Quality Score: {quality_score:.1f}")
                    )
                    
            elif options['all']:
                # Process all videos
                self.stdout.write("Processing all videos in media directory...")
                results = audio_service.process_all_videos()
                
                successful_results = [r for r in results if 'error' not in r]
                successful_count = len(successful_results)
                total_count = len(results)
                
                avg_quality = 0
                if successful_count > 0:
                    avg_quality = sum(r['quality_analysis']['quality_score'] for r in successful_results) / successful_count
                
                self.stdout.write(
                    self.style.SUCCESS(f"Processed {successful_count}/{total_count} videos successfully")
                )
                self.stdout.write(f"Average quality score of successful videos: {avg_quality:.2f}")
                
            elif options['report']:
                # Generate report only
                self.stdout.write("Generating audio quality report...")
                results = audio_service.process_all_videos()
                
                successful_results = [r for r in results if 'error' not in r]
                total_count = len(results)

                if successful_results:
                    quality_scores = [r['quality_analysis']['quality_score'] for r in successful_results]
                    avg_quality = sum(quality_scores) / len(quality_scores)
                    
                    distribution = {
                        'excellent': len([s for s in quality_scores if s >= 80]),
                        'good': len([s for s in quality_scores if 60 <= s < 80]),
                        'fair': len([s for s in quality_scores if 40 <= s < 60]),
                        'poor': len([s for s in quality_scores if s < 40])
                    }
                    
                    self.stdout.write("\n" + "="*50)
                    self.stdout.write("AUDIO QUALITY REPORT")
                    self.stdout.write("="*50)
                    self.stdout.write(f"Total videos found: {total_count}")
                    self.stdout.write(f"Successfully processed: {len(successful_results)}")
                    self.stdout.write(f"Average quality score: {avg_quality:.2f}")
                    self.stdout.write("\nQuality Distribution:")
                    self.stdout.write(f"  Excellent (80-100): {distribution['excellent']}")
                    self.stdout.write(f"  Good (60-79):      {distribution['good']}")
                    self.stdout.write(f"  Fair (40-59):      {distribution['fair']}")
                    self.stdout.write(f"  Poor (0-39):       {distribution['poor']}")
                    
                    sorted_results = sorted(successful_results, key=lambda x: x['quality_analysis']['quality_score'], reverse=True)
                    
                    if sorted_results:
                        self.stdout.write(f"\nBest quality: {os.path.basename(sorted_results[0]['video_file'])} ({sorted_results[0]['quality_analysis']['quality_score']:.1f})")
                        self.stdout.write(f"Worst quality: {os.path.basename(sorted_results[-1]['video_file'])} ({sorted_results[-1]['quality_analysis']['quality_score']:.1f})")
                else:
                    self.stdout.write(self.style.WARNING("No videos could be processed to generate a report."))
            else:
                raise CommandError("Please specify --video, --all, or --report")
            
            # Save results to file if requested
            if options['output'] and results:
                with open(options['output'], 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                self.stdout.write(f"Full results saved to {options['output']}")
            
            self.stdout.write(self.style.SUCCESS("Command completed."))
            
        except Exception as e:
            raise CommandError(f"Command failed unexpectedly: {str(e)}")