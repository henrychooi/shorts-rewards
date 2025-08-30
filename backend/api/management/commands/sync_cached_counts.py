"""
Management command to sync cached like_count and comment_count with actual database counts
"""
from django.core.management.base import BaseCommand
from api.models import Short


class Command(BaseCommand):
    help = 'Sync cached like_count and comment_count with actual database counts for all shorts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        shorts = Short.objects.all()
        updated_count = 0
        
        for short in shorts:
            actual_like_count = short.like_count_calculated
            actual_comment_count = short.comment_count_calculated
            
            like_count_changed = short.like_count != actual_like_count
            comment_count_changed = short.comment_count != actual_comment_count
            
            if like_count_changed or comment_count_changed:
                self.stdout.write(
                    f"Short ID {short.id} ({short.title or 'Untitled'}): "
                    f"Like count: {short.like_count} -> {actual_like_count}, "
                    f"Comment count: {short.comment_count} -> {actual_comment_count}"
                )
                
                if not dry_run:
                    short.like_count = actual_like_count
                    short.comment_count = actual_comment_count
                    short.save(update_fields=['like_count', 'comment_count'])
                
                updated_count += 1
        
        if updated_count == 0:
            self.stdout.write(self.style.SUCCESS('All cached counts are already in sync!'))
        else:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f'Would update {updated_count} shorts. Run without --dry-run to apply changes.')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully synced cached counts for {updated_count} shorts.')
                )
