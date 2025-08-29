import os
import time
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from api.models import Short, VideoAnalysisLog
from api.video_analysis_service import VideoAnalysisService
import json


class Command(BaseCommand):
    help = 'Analyze video content using Google Gemini AI to evaluate quality metrics'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--video',
            type=str,
            help='Analyze a specific video by Short ID (UUID)',
        )
        parser.add_argument(
            '--filename',
            type=str,
            help='Analyze a specific video by filename',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Analyze all videos that need analysis',
        )
        parser.add_argument(
            '--reanalyze',
            action='store_true',
            help='Re-analyze videos even if already processed',
        )
        parser.add_argument(
            '--report',
            action='store_true',
            help='Generate analysis report only (no processing)',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path for detailed results (JSON format)',
        )
        parser.add_argument(
            '--model',
            type=str,
            default='gemini-1.5-pro',
            help='Gemini model to use (default: gemini-1.5-pro)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually processing',
        )
    
    def handle(self, *args, **options):
        try:
            # Initialize video analysis service
            self.stdout.write("Initializing Video Analysis Service...")
            
            # Check for API key
            api_key = getattr(settings, 'GOOGLE_AI_API_KEY', None)
            if not api_key:
                raise CommandError(
                    "Google AI API key not found. Please set GOOGLE_AI_API_KEY in your settings."
                )
            
            video_service = VideoAnalysisService(
                api_key=api_key,
                model_name=options['model']
            )
            
            results = []
            
            if options['video']:
                # Process single video by Short ID
                results = self._process_single_video_by_id(
                    video_service, options['video'], options['dry_run']
                )
                
            elif options['filename']:
                # Process single video by filename
                results = self._process_single_video_by_filename(
                    video_service, options['filename'], options['dry_run']
                )
                
            elif options['all']:
                # Process all videos
                results = self._process_all_videos(
                    video_service, options['reanalyze'], options['dry_run']
                )
                
            elif options['report']:
                # Generate report only
                self._generate_analysis_report()
                return
                
            else:
                raise CommandError(
                    "Please specify --video, --filename, --all, or --report"
                )
            
            # Summary output
            self._display_summary(results)
            
            # Save detailed results if requested
            if options['output'] and results:
                with open(options['output'], 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                self.stdout.write(f"Detailed results saved to {options['output']}")
            
            self.stdout.write(
                self.style.SUCCESS("Video analysis command completed successfully.")
            )
            
        except Exception as e:
            raise CommandError(f"Command failed: {str(e)}")
    
    def _process_single_video_by_id(self, video_service, short_id, dry_run=False):
        """Process a single video by Short ID"""
        try:
            short = Short.objects.get(id=short_id)
            
            if not short.video_exists():
                self.stdout.write(
                    self.style.ERROR(f"Video file not found for Short: {short.title}")
                )
                return []
            
            video_path = short.video.path
            self.stdout.write(f"Processing video: {short.title} ({os.path.basename(video_path)})")
            
            if dry_run:
                self.stdout.write(self.style.WARNING("DRY RUN - No actual processing"))
                return [{
                    'short_id': str(short.id),
                    'title': short.title,
                    'status': 'would_process'
                }]
            
            return self._analyze_video(video_service, short, video_path)
            
        except Short.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Short with ID {short_id} not found")
            )
            return []
    
    def _process_single_video_by_filename(self, video_service, filename, dry_run=False):
        """Process a single video by filename"""
        # Find Short with matching video filename
        shorts = Short.objects.filter(video__icontains=filename)
        
        if not shorts.exists():
            self.stdout.write(
                self.style.ERROR(f"No Short found with video filename: {filename}")
            )
            return []
        
        if shorts.count() > 1:
            self.stdout.write(
                self.style.WARNING(f"Multiple Shorts found with filename '{filename}':")
            )
            for short in shorts:
                self.stdout.write(f"  - {short.id}: {short.title}")
            
            short = shorts.first()
            self.stdout.write(f"Processing first match: {short.title}")
        else:
            short = shorts.first()
        
        if not short.video_exists():
            self.stdout.write(
                self.style.ERROR(f"Video file not found for Short: {short.title}")
            )
            return []
        
        video_path = short.video.path
        self.stdout.write(f"Processing video: {short.title} ({os.path.basename(video_path)})")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No actual processing"))
            return [{
                'short_id': str(short.id),
                'title': short.title,
                'status': 'would_process'
            }]
        
        return self._analyze_video(video_service, short, video_path)
    
    def _process_all_videos(self, video_service, reanalyze=False, dry_run=False):
        """Process all videos that need analysis"""
        # Get videos that need analysis
        if reanalyze:
            shorts_to_process = Short.objects.filter(is_active=True)
            self.stdout.write(f"Re-analyzing all {shorts_to_process.count()} active videos...")
        else:
            shorts_to_process = Short.objects.filter(
                is_active=True,
                video_analysis_status__in=['pending', 'failed']
            )
            self.stdout.write(f"Found {shorts_to_process.count()} videos needing analysis...")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No actual processing"))
            return [{
                'short_id': str(short.id),
                'title': short.title,
                'status': 'would_process'
            } for short in shorts_to_process]
        
        results = []
        total_count = shorts_to_process.count()
        
        for i, short in enumerate(shorts_to_process, 1):
            self.stdout.write(f"\n[{i}/{total_count}] Processing: {short.title}")
            
            if not short.video_exists():
                self.stdout.write(
                    self.style.WARNING(f"Skipping {short.title} - video file missing")
                )
                continue
            
            video_path = short.video.path
            result = self._analyze_video(video_service, short, video_path)
            results.append(result)
            
            # Add delay to avoid rate limits
            if i < total_count:
                self.stdout.write("Waiting 2 seconds before next video...")
                time.sleep(2)
        
        return results
    
    def _analyze_video(self, video_service, short, video_path):
        """Analyze a single video and update the Short model"""
        # Create analysis log
        analysis_log = VideoAnalysisLog.objects.create(
            short=short,
            analysis_type='manual' if hasattr(self, '_manual_trigger') else 'initial',
            file_size_mb=os.path.getsize(video_path) / (1024 * 1024)
        )
        
        try:
            # Update status to processing
            short.video_analysis_status = 'processing'
            short.save(update_fields=['video_analysis_status'])
            
            # Process the video
            analysis_result = video_service.process_single_video(video_path)
            
            if 'error' in analysis_result:
                self.stdout.write(
                    self.style.ERROR(f"Error analyzing {short.title}: {analysis_result['error']}")
                )
                
                # Log the failure
                analysis_log.mark_completed(
                    success=False, 
                    error_message=analysis_result['error'],
                    result=analysis_result
                )
                
                # Update short with error
                short.update_video_analysis(analysis_result)
                
                return {
                    'short_id': str(short.id),
                    'title': short.title,
                    'status': 'error',
                    'error': analysis_result['error']
                }
            
            # Success - update the Short model
            metrics = video_service.get_quality_metrics_summary(analysis_result)
            short.update_video_analysis(analysis_result)
            
            # Log the success
            analysis_log.mark_completed(
                success=True,
                result=analysis_result
            )
            
            quality_score = analysis_result.get('overall_quality_score', 0)
            engagement_score = analysis_result.get('engagement_score', 0)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {short.title} - Quality: {quality_score:.1f} | "
                    f"Engagement: {engagement_score:.1f} | Grade: {short.get_quality_grade()}"
                )
            )
            
            return {
                'short_id': str(short.id),
                'title': short.title,
                'status': 'success',
                'quality_score': quality_score,
                'engagement_score': engagement_score,
                'grade': short.get_quality_grade(),
                'summary': analysis_result.get('summary', ''),
                'processed_at': analysis_result.get('processed_at')
            }
            
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            
            self.stdout.write(
                self.style.ERROR(f"Error processing {short.title}: {error_msg}")
            )
            
            # Log the failure
            analysis_log.mark_completed(
                success=False,
                error_message=error_msg
            )
            
            # Update short status
            short.video_analysis_status = 'failed'
            short.video_analysis_error = error_msg
            short.video_processed_at = timezone.now()
            short.save(update_fields=[
                'video_analysis_status', 
                'video_analysis_error', 
                'video_processed_at'
            ])
            
            return {
                'short_id': str(short.id),
                'title': short.title,
                'status': 'error',
                'error': error_msg
            }
    
    def _generate_analysis_report(self):
        """Generate comprehensive analysis report"""
        self.stdout.write("Generating Video Analysis Report...")
        
        # Get all shorts with analysis data
        analyzed_shorts = Short.objects.filter(
            video_analysis_status='completed',
            video_quality_score__isnull=False
        )
        
        if not analyzed_shorts.exists():
            self.stdout.write(
                self.style.WARNING("No analyzed videos found to generate report.")
            )
            return
        
        total_videos = analyzed_shorts.count()
        
        # Calculate metrics
        quality_scores = [s.video_quality_score for s in analyzed_shorts if s.video_quality_score]
        engagement_scores = [s.engagement_score for s in analyzed_shorts if s.engagement_score]
        technical_scores = [s.technical_score for s in analyzed_shorts if s.technical_score]
        
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        avg_engagement = sum(engagement_scores) / len(engagement_scores) if engagement_scores else 0
        avg_technical = sum(technical_scores) / len(technical_scores) if technical_scores else 0
        
        # Grade distribution
        grades = {}
        for short in analyzed_shorts:
            grade = short.get_quality_grade()
            grades[grade] = grades.get(grade, 0) + 1
        
        # Quality distribution
        quality_distribution = {
            'excellent': len([s for s in quality_scores if s >= 90]),
            'very_good': len([s for s in quality_scores if 80 <= s < 90]),
            'good': len([s for s in quality_scores if 70 <= s < 80]),
            'fair': len([s for s in quality_scores if 60 <= s < 70]),
            'needs_improvement': len([s for s in quality_scores if s < 60])
        }
        
        # Category distribution
        categories = {}
        for short in analyzed_shorts:
            cat = short.content_category or 'unknown'
            categories[cat] = categories.get(cat, 0) + 1
        
        # Display report
        self.stdout.write("\n" + "="*60)
        self.stdout.write("VIDEO ANALYSIS REPORT")
        self.stdout.write("="*60)
        
        self.stdout.write(f"\nOverall Statistics:")
        self.stdout.write(f"  Total analyzed videos: {total_videos}")
        self.stdout.write(f"  Average quality score: {avg_quality:.2f}")
        self.stdout.write(f"  Average engagement score: {avg_engagement:.2f}")
        self.stdout.write(f"  Average technical score: {avg_technical:.2f}")
        
        self.stdout.write(f"\nGrade Distribution:")
        for grade, count in sorted(grades.items()):
            percentage = (count / total_videos) * 100
            self.stdout.write(f"  {grade}: {count} videos ({percentage:.1f}%)")
        
        self.stdout.write(f"\nQuality Distribution:")
        for category, count in quality_distribution.items():
            percentage = (count / len(quality_scores)) * 100 if quality_scores else 0
            self.stdout.write(f"  {category.replace('_', ' ').title()}: {count} ({percentage:.1f}%)")
        
        self.stdout.write(f"\nContent Categories:")
        for category, count in sorted(categories.items()):
            percentage = (count / total_videos) * 100
            self.stdout.write(f"  {category.title()}: {count} ({percentage:.1f}%)")
        
        # Top performers
        top_quality = analyzed_shorts.order_by('-video_quality_score')[:3]
        top_engagement = analyzed_shorts.order_by('-engagement_score')[:3]
        
        self.stdout.write(f"\nTop Quality Videos:")
        for i, short in enumerate(top_quality, 1):
            self.stdout.write(
                f"  {i}. {short.title} - {short.video_quality_score:.1f} ({short.get_quality_grade()})"
            )
        
        self.stdout.write(f"\nTop Engagement Potential:")
        for i, short in enumerate(top_engagement, 1):
            self.stdout.write(
                f"  {i}. {short.title} - {short.engagement_score:.1f}"
            )
        
        # Videos needing attention
        low_quality = analyzed_shorts.filter(video_quality_score__lt=60).order_by('video_quality_score')[:5]
        
        if low_quality.exists():
            self.stdout.write(f"\nVideos Needing Improvement:")
            for short in low_quality:
                self.stdout.write(
                    f"  - {short.title}: {short.video_quality_score:.1f} "
                    f"({short.get_quality_grade()}) - {short.video_analysis_summary[:50]}..."
                )
        
        # Processing statistics
        failed_count = Short.objects.filter(video_analysis_status='failed').count()
        pending_count = Short.objects.filter(video_analysis_status='pending').count()
        
        self.stdout.write(f"\nProcessing Status:")
        self.stdout.write(f"  Completed: {total_videos}")
        self.stdout.write(f"  Failed: {failed_count}")
        self.stdout.write(f"  Pending: {pending_count}")
        
        self.stdout.write("="*60)
    
    def _display_summary(self, results):
        """Display processing summary"""
        if not results:
            return
        
        successful = [r for r in results if r.get('status') == 'success']
        failed = [r for r in results if r.get('status') == 'error']
        
        self.stdout.write(f"\n" + "="*50)
        self.stdout.write("PROCESSING SUMMARY")
        self.stdout.write("="*50)
        
        self.stdout.write(f"Total processed: {len(results)}")
        self.stdout.write(f"Successful: {len(successful)}")
        self.stdout.write(f"Failed: {len(failed)}")
        
        if successful:
            avg_quality = sum(r['quality_score'] for r in successful if 'quality_score' in r) / len(successful)
            avg_engagement = sum(r['engagement_score'] for r in successful if 'engagement_score' in r) / len(successful)
            
            self.stdout.write(f"Average quality score: {avg_quality:.2f}")
            self.stdout.write(f"Average engagement score: {avg_engagement:.2f}")
            
            # Grade distribution
            grades = {}
            for result in successful:
                grade = result.get('grade', 'F')
                grades[grade] = grades.get(grade, 0) + 1
            
            self.stdout.write(f"Grade distribution:")
            for grade, count in sorted(grades.items()):
                self.stdout.write(f"  {grade}: {count}")
        
        if failed:
            self.stdout.write(f"\nFailed videos:")
            for result in failed[:5]:  # Show first 5 failures
                self.stdout.write(f"  - {result['title']}: {result.get('error', 'Unknown error')}")
            
            if len(failed) > 5:
                self.stdout.write(f"  ... and {len(failed) - 5} more")
        
        self.stdout.write("="*50)