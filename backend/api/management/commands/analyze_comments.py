import logging
import os
import sys
from django.core.management.base import BaseCommand, CommandError

# Add the project path to sys.path to import from the api package
project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_path not in sys.path:
    sys.path.insert(0, project_path)

from ...models import Comment, Short
from ...comment_analysis_service import CommentAnalysisService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to analyze sentiment of comments.

    Usage:
        python manage.py analyze_comments --all                    # Analyze all unanalyzed comments
        python manage.py analyze_comments --short <short_id>       # Analyze comments for specific short
        python manage.py analyze_comments --comment <comment_id>   # Analyze specific comment
        python manage.py analyze_comments --batch <size>           # Process in batches
        python manage.py analyze_comments --force                  # Re-analyze already processed comments
    """

    help = 'Analyze sentiment of comments using Hugging Face transformers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Analyze all unanalyzed comments',
        )

        parser.add_argument(
            '--short',
            type=str,
            help='Analyze comments for specific short (by ID)',
        )

        parser.add_argument(
            '--comment',
            type=str,
            help='Analyze specific comment (by ID)',
        )

        parser.add_argument(
            '--batch',
            type=int,
            default=50,
            help='Batch size for processing (default: 50)',
        )

        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-analyze already processed comments',
        )

        parser.add_argument(
            '--update-aggregate',
            action='store_true',
            default=True,
            help='Update aggregate comment score for shorts',
        )

    def handle(self, *args, **options):
        """Execute the command"""
        if not any([options['all'], options['short'], options['comment']]):
            raise CommandError('Must specify --all, --short, or --comment')

        try:
            service = CommentAnalysisService()

            if options['comment']:
                self.analyze_single_comment(service, options['comment'], options['force'])
            elif options['short']:
                self.analyze_short_comments(service, options['short'], options['force'], options['update_aggregate'])
            elif options['all']:
                self.analyze_all_comments(service, options['batch'], options['force'], options['update_aggregate'])

        except Exception as e:
            logger.error(f"Command failed: {str(e)}")
            raise CommandError(f"Analysis failed: {str(e)}")

    def analyze_single_comment(self, service: CommentAnalysisService, comment_id: str, force: bool = False):
        """Analyze a single comment by ID"""
        try:
            comment = Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            raise CommandError(f'Comment with ID {comment_id} does not exist')

        self.stdout.write(f'Analyzing comment {comment_id}...')

        result = service.reanalyze_comment(comment, force=force)

        if result.get('error'):
            self.stderr.write(f'Error analyzing comment {comment_id}: {result["error"]}')
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'Comment {comment_id} analyzed successfully. '
                f'Score: {result["sentiment_score"]:.2f}, '
                f'Label: {result["sentiment_label"]}'
            )
        )

    def analyze_short_comments(self, service: CommentAnalysisService, short_id: str, force: bool = False, update_aggregate: bool = True):
        """Analyze all comments for a specific short"""
        try:
            short = Short.objects.get(id=short_id)
        except Short.DoesNotExist:
            raise CommandError(f'Short with ID {short_id} does not exist')

        self.stdout.write(f'Analyzing comments for short: {short.title or "Untitled"} (ID: {short_id})')

        # Get comments to analyze
        query = short.comments.filter(is_active=True)
        if not force:
            query = query.filter(sentiment_score__isnull=True)

        total_comments = query.count()
        if total_comments == 0:
            self.stdout.write('No comments to analyze')
            return

        self.stdout.write(f'Found {total_comments} comments to analyze')

        analyzed_count = 0
        error_count = 0
        total_score = 0

        for comment in query:
            result = service.analyze_comment_instance(comment)

            if result.get('error'):
                error_count += 1
                self.stderr.write(f'Error analyzing comment {comment.id}: {result["error"]}')
            else:
                analyzed_count += 1
                total_score += result['sentiment_score'] or 0

            # Update progress
            if (analyzed_count + error_count) % 10 == 0:
                self.stdout.write(f'Processed {analyzed_count + error_count}/{total_comments} comments...')

        # Update aggregate score if requested
        if update_aggregate and analyzed_count > 0:
            aggregate_score = total_score / analyzed_count
            short.comment_analysis_score = aggregate_score
            short.save(update_fields=['comment_analysis_score'])

            self.stdout.write(
                self.style.SUCCESS(
                    f'Short {short_id} analysis complete. '
                    f'Analyzed: {analyzed_count}, '
                    f'Errors: {error_count}, '
                    f'Aggregate score: {aggregate_score:.2f}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Short {short_id} analysis complete. '
                    f'Analyzed: {analyzed_count}, '
                    f'Errors: {error_count}'
                )
            )

    def analyze_all_comments(self, service: CommentAnalysisService, batch_size: int = 50, force: bool = False, update_aggregate: bool = True):
        """Analyze all unanalyzed comments in the system"""
        self.stdout.write('Starting batch analysis of all comments...')

        # Get comments to analyze
        query = Comment.objects.filter(is_active=True)
        if not force:
            query = query.filter(sentiment_score__isnull=True)

        total_comments = query.count()
        if total_comments == 0:
            self.stdout.write('No comments to analyze')
            return

        self.stdout.write(f'Found {total_comments} comments to analyze. Processing in batches of {batch_size}...')

        analyzed_count = 0
        error_count = 0
        processed_count = 0
        short_scores = {}  # Track scores per short for aggregate calculation

        # Process in batches
        for i in range(0, total_comments, batch_size):
            batch = query[i:i + batch_size]
            batch_analyzed = 0
            batch_errors = 0

            for comment in batch:
                result = service.analyze_comment_instance(comment)

                if result.get('error'):
                    error_count += 1
                    batch_errors += 1
                else:
                    analyzed_count += 1
                    batch_analyzed += 1
                    score = result['sentiment_score'] or 0
                    total_score += score

                    # Track scores per short
                    short_id = str(comment.short.id)
                    if short_id not in short_scores:
                        short_scores[short_id] = []
                    short_scores[short_id].append(score)

            processed_count += len(batch)

            self.stdout.write(
                f'Batch {i//batch_size + 1} complete: '
                f'Analyzed: {batch_analyzed}, '
                f'Errors: {batch_errors}, '
                f'Total progress: {processed_count}/{total_comments} ({processed_count/total_comments*100:.1f}%)'
            )

        # Update aggregate scores for each short
        if update_aggregate and short_scores:
            shorts_updated = 0
            for short_id, scores in short_scores.items():
                if scores:
                    aggregate_score = sum(scores) / len(scores)
                    Short.objects.filter(id=short_id).update(comment_analysis_score=aggregate_score)
                    shorts_updated += 1

            self.stdout.write(f'Updated aggregate scores for {shorts_updated} shorts')

        self.stdout.write(
            self.style.SUCCESS(
                f'Analysis complete! '
                f'Total analyzed: {analyzed_count}, '
                f'Total errors: {error_count}, '
                f'Success rate: {(analyzed_count/total_comments*100):.1f}%'
            )
        )
