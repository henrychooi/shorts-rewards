from django.core.management.base import BaseCommand
from decimal import Decimal
from api.models import PlatformRevenue
from datetime import datetime


class Command(BaseCommand):
    help = 'Set platform revenue for a specific month'

    def add_arguments(self, parser):
        parser.add_argument(
            '--revenue',
            type=float,
            required=True,
            help='Platform revenue amount'
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Year (default: current year)'
        )
        parser.add_argument(
            '--month',
            type=int,
            help='Month (default: current month)'
        )
        parser.add_argument(
            '--sources',
            type=str,
            help='Revenue sources as JSON string (optional)'
        )

    def handle(self, *args, **options):
        revenue = Decimal(str(options['revenue']))
        now = datetime.now()
        year = options.get('year', now.year)
        month = options.get('month', now.month)
        
        # Parse revenue sources if provided
        revenue_sources = {}
        if options.get('sources'):
            import json
            try:
                revenue_sources = json.loads(options['sources'])
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR('Invalid JSON for revenue sources'))
                return
        
        # Create or update platform revenue
        platform_revenue, created = PlatformRevenue.objects.update_or_create(
            year=year,
            month=month,
            defaults={
                'total_revenue': revenue,
                'revenue_sources': revenue_sources,
                'creator_share_percentage': Decimal('50.00'),  # 50% to creators
                'is_finalized': True
            }
        )
        
        action = "Created" if created else "Updated"
        
        self.stdout.write(self.style.SUCCESS(f'💰 {action} Platform Revenue'))
        self.stdout.write(f'📅 Period: {year}-{month:02d}')
        self.stdout.write(f'💵 Total Revenue: ${revenue:,}')
        self.stdout.write(f'👥 Creator Pool (50%): ${platform_revenue.creator_pool:,}')
        self.stdout.write(f'🏢 Platform Keeps: ${platform_revenue.platform_keeps:,}')
        
        if revenue_sources:
            self.stdout.write(f'\n📊 Revenue Sources:')
            for source, amount in revenue_sources.items():
                self.stdout.write(f'   {source}: ${amount:,}')
        
        self.stdout.write(f'\n🚀 Now you can process payouts:')
        self.stdout.write(f'   python manage.py test_3min_payout --revenue {revenue}')
        self.stdout.write(f'   OR')
        self.stdout.write(f'   python manage.py process_monthly_payouts --year {year} --month {month}')
        
        # Show current platform revenues
        self.stdout.write(f'\n📋 All Platform Revenues:')
        all_revenues = PlatformRevenue.objects.all()[:5]
        for rev in all_revenues:
            status = "✅ Finalized" if rev.is_finalized else "⏳ Draft"
            payouts = "💰 Paid" if rev.payouts_processed else "🔄 Pending"
            self.stdout.write(f'   {rev.period_display}: ${rev.total_revenue:,} ({status}, {payouts})')
