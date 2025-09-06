from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import Wallet, Transaction
from decimal import Decimal


class Command(BaseCommand):
    help = 'Fix wallet balances and total_earnings based on existing transactions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        wallets = Wallet.objects.all()
        updated_count = 0
        
        for wallet in wallets:
            # Calculate correct balance from all transactions (confirmed or not)
            transactions = wallet.transactions.all()
            correct_balance = sum((t.amount for t in transactions), Decimal('0.00'))
            
            # Calculate correct total earnings - sum of all positive earnings minus withdrawn amounts
            # Only count positive earnings (rewards, bonuses, payouts)
            positive_earnings = sum((t.amount for t in transactions if t.amount > 0), Decimal('0.00'))
            # Sum of all withdrawals (negative amounts)
            withdrawals = sum((abs(t.amount) for t in transactions if t.amount < 0 and t.transaction_type == 'withdrawal'), Decimal('0.00'))
            # Total earnings should be cumulative positive earnings minus what was withdrawn
            correct_total_earnings = positive_earnings
            
            # Check if update is needed
            needs_update = (
                wallet.balance != correct_balance or 
                wallet.total_earnings != correct_total_earnings
            )
            
            if needs_update:
                self.stdout.write(
                    f"Wallet for {wallet.user.username}:\n"
                    f"  Current balance: ${wallet.balance} -> ${correct_balance}\n"
                    f"  Current total_earnings: ${wallet.total_earnings} -> ${correct_total_earnings}\n"
                    f"  Transaction count: {transactions.count()}"
                )
                
                if not dry_run:
                    with transaction.atomic():
                        wallet.balance = correct_balance
                        wallet.total_earnings = correct_total_earnings
                        wallet.save(update_fields=['balance', 'total_earnings'])
                
                updated_count += 1
        
        if updated_count == 0:
            self.stdout.write(self.style.SUCCESS('All wallets are already correct!'))
        else:
            action = "Would update" if dry_run else "Updated"
            self.stdout.write(
                self.style.SUCCESS(f'{action} {updated_count} wallet(s)')
            )
