from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from api.models import MonthlyPayout, PlatformRevenue, Transaction

class Command(BaseCommand):
    help = 'Clears monthly payouts and associated transactions for a specific period.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            required=True,
            help='Year of the payout period to clear (e.g., 2025)'
        )
        parser.add_argument(
            '--month',
            type=int,
            required=True,
            help='Month of the payout period to clear (1-12)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleared without actually deleting anything.'
        )

    def handle(self, *args, **options):
        year = options['year']
        month = options['month']
        dry_run = options['dry_run']

        if month < 1 or month > 12:
            raise CommandError('Month must be between 1 and 12.')

        self.stdout.write(
            self.style.WARNING(
                f'Attempting to clear payouts for {year}-{month:02d}'
            )
        )

        try:
            with transaction.atomic():
                payouts_to_delete = MonthlyPayout.objects.filter(
                    payout_year=year,
                    payout_month=month
                )
                payout_count = payouts_to_delete.count()

                if payout_count == 0:
                    self.stdout.write(self.style.SUCCESS(f'No payouts found for {year}-{month:02d}. Nothing to do.'))
                    return

                self.stdout.write(f'Found {payout_count} payout records to delete.')

                transaction_ids = list(payouts_to_delete.values_list(
                    'payout_transaction_id', flat=True
                ))
                transaction_ids = [tid for tid in transaction_ids if tid is not None]

                if transaction_ids:
                    self.stdout.write(f'Found {len(transaction_ids)} associated transactions to delete.')

                platform_revenue = PlatformRevenue.objects.filter(year=year, month=month).first()
                if platform_revenue:
                    self.stdout.write('Found a platform revenue record to reset.')

                if not dry_run:
                    # Delete transactions
                    if transaction_ids:
                        transactions_deleted, _ = Transaction.objects.filter(id__in=transaction_ids).delete()
                        self.stdout.write(f'Deleted {transactions_deleted} transactions.')

                    # Delete payouts
                    payouts_deleted, _ = payouts_to_delete.delete()
                    self.stdout.write(f'Deleted {payouts_deleted} payouts.')

                    # Reset platform revenue
                    if platform_revenue:
                        platform_revenue.is_finalized = False
                        platform_revenue.payouts_processed = False
                        platform_revenue.processed_at = None
                        platform_revenue.save()
                        self.stdout.write('Reset platform revenue record.')
                    
                    self.stdout.write(self.style.SUCCESS(f'Successfully cleared data for {year}-{month:02d}.'))

                else:
                    self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes were made.'))
                    self.stdout.write(f'Would delete {payout_count} payouts.')
                    if transaction_ids:
                        self.stdout.write(f'Would delete {len(transaction_ids)} transactions.')
                    if platform_revenue:
                        self.stdout.write('Would reset the platform revenue record.')
                    transaction.set_rollback(True)

        except Exception as e:
            raise CommandError(f'An error occurred: {str(e)}')
