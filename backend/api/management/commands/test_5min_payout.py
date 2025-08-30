from django.core.management.base import BaseCommand
from decimal import Decimal
from api.reward_service import monthly_revenue_service


class Command(BaseCommand):
    help = 'Test 5-minute payout system - quick way to test monthly revenue sharing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--revenue',
            type=float,
            default=1000,
            help='Platform revenue to test with (default: 1000)'
        )
        parser.add_argument(
            '--real',
            action='store_true',
            help='Create real transactions (default: dry run)'
        )

    def handle(self, *args, **options):
        revenue = Decimal(str(options['revenue']))
        dry_run = not options['real']
        
        self.stdout.write(self.style.SUCCESS('🚀 5-Minute Payout Test'))
        self.stdout.write(f'⏱️  Testing payouts for videos uploaded in the last 5 minutes')
        self.stdout.write(f'💰 Platform Revenue: ${revenue}')
        self.stdout.write(f'🎯 Mode: {"🔥 REAL TRANSACTIONS" if not dry_run else "🧪 DRY RUN"}')
        
        result = monthly_revenue_service.test_5minute_payout(
            platform_revenue=revenue,
            dry_run=dry_run
        )
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f"\n✅ {result['message']}"))
            
            # Show payouts
            payouts = result.get('payouts', {})
            if payouts:
                self.stdout.write(f"\n👥 Creator Payouts (Last 5 Minutes):")
                
                for creator_id, payout_data in payouts.items():
                    username = payout_data['username']
                    total_points = payout_data['total_points']
                    avg_points = payout_data['average_points']
                    amount = payout_data['payout_amount']
                    avg_percentage = payout_data['average_points_percentage']
                    video_count = payout_data['video_count']
                    
                    self.stdout.write(
                        f"   💰 {username}: ${amount:.2f} "
                        f"({avg_points:.2f} avg points = {avg_percentage:.1f}%, {video_count} videos)"
                    )
                
                self.stdout.write(f"\n📊 Summary:")
                self.stdout.write(f"   Total Average Points: {result['total_creator_average_points']:.2f}")
                self.stdout.write(f"   Creator Pool (50%): ${result['creators_pool']}")
                self.stdout.write(f"   Platform Keeps (50%): ${result['platform_keeps']}")
                self.stdout.write(f"   💡 Now using AVERAGE points per video for fair distribution!")
                
                if dry_run:
                    self.stdout.write(f"\n🔥 To create REAL payouts:")
                    self.stdout.write(f"   python manage.py test_5min_payout --revenue {revenue} --real")
                else:
                    self.stdout.write(f"\n✅ Check wallets for the real payouts!")
                    
            else:
                self.stdout.write(self.style.WARNING("⚠️ No creators found"))
                
        else:
            self.stdout.write(self.style.ERROR(f"❌ {result.get('message', result.get('error'))}"))
            if 'suggestion' in result:
                self.stdout.write(f"💡 {result['suggestion']}")
        
        self.stdout.write(f"\n🎯 Quick Commands:")
        self.stdout.write(f"   Dry run:  python manage.py test_5min_payout")
        self.stdout.write(f"   Real run: python manage.py test_5min_payout --real")
        self.stdout.write(f"   Custom:   python manage.py test_5min_payout --revenue 500 --real")
