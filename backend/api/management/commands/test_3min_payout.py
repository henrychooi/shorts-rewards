from django.core.management.base import BaseCommand
from decimal import Decimal
from api.reward_service import monthly_revenue_service


class Command(BaseCommand):
    help = 'Test 3-minute payout system - quick way to test monthly revenue sharing'

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
        
        self.stdout.write(self.style.SUCCESS('🚀 3-Minute Payout Test'))
        self.stdout.write(f'⏱️  Testing payouts for videos uploaded in the last 3 minutes')
        self.stdout.write(f'💰 Platform Revenue: ${revenue}')
        self.stdout.write(f'🎯 Mode: {"🔥 REAL TRANSACTIONS" if not dry_run else "🧪 DRY RUN"}')
        
        result = monthly_revenue_service.test_3minute_payout(
            platform_revenue=revenue,
            dry_run=dry_run
        )
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f"\n✅ {result['message']}"))
            
            # Show payouts
            payouts = result.get('payouts', {})
            if payouts:
                self.stdout.write(f"\n👥 Creator Payouts (Last 3 Minutes):")
                
                for creator_id, payout_data in payouts.items():
                    username = payout_data['username']
                    points = payout_data['total_points']
                    amount = payout_data['payout_amount']
                    percentage = payout_data['points_percentage']
                    shorts_count = payout_data['shorts_count']
                    
                    self.stdout.write(
                        f"   💰 {username}: ${amount:.2f} "
                        f"({points} points = {percentage:.1%}, {shorts_count} videos)"
                    )
                
                self.stdout.write(f"\n📊 Summary:")
                self.stdout.write(f"   Total Points: {result['total_creator_points']}")
                self.stdout.write(f"   Creator Pool (50%): ${result['creators_pool']}")
                self.stdout.write(f"   Platform Keeps (50%): ${result['platform_keeps']}")
                
                if dry_run:
                    self.stdout.write(f"\n🔥 To create REAL payouts:")
                    self.stdout.write(f"   python manage.py test_3min_payout --revenue {revenue} --real")
                else:
                    self.stdout.write(f"\n✅ Check wallets for the real payouts!")
                    
            else:
                self.stdout.write(self.style.WARNING("⚠️ No creators found"))
                
        else:
            self.stdout.write(self.style.ERROR(f"❌ {result.get('message', result.get('error'))}"))
            if 'suggestion' in result:
                self.stdout.write(f"💡 {result['suggestion']}")
        
        self.stdout.write(f"\n🎯 Quick Commands:")
        self.stdout.write(f"   Dry run:  python manage.py test_3min_payout")
        self.stdout.write(f"   Real run: python manage.py test_3min_payout --real")
        self.stdout.write(f"   Custom:   python manage.py test_3min_payout --revenue 500 --real")
