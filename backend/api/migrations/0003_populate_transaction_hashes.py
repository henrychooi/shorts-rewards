# Generated migration to handle transaction_hash for existing records
from django.db import migrations, models
import uuid
import hashlib
import json
from datetime import datetime

def populate_transaction_hashes(apps, schema_editor):
    """Populate transaction_hash for existing transactions"""
    Transaction = apps.get_model('api', 'Transaction')
    
    for transaction in Transaction.objects.all():
        # Generate a hash for existing transactions
        transaction_data = {
            'id': str(transaction.id),
            'wallet_id': transaction.wallet.id,
            'transaction_type': transaction.transaction_type,
            'amount': str(transaction.amount),
            'description': transaction.description,
            'timestamp': transaction.created_at.isoformat() if transaction.created_at else datetime.now().isoformat(),
            'nonce': 0
        }
        
        transaction_string = json.dumps(transaction_data, sort_keys=True)
        transaction_hash = hashlib.sha256(transaction_string.encode()).hexdigest()
        
        transaction.transaction_hash = transaction_hash
        transaction.save()

def reverse_populate_transaction_hashes(apps, schema_editor):
    """Reverse operation - clear transaction hashes"""
    Transaction = apps.get_model('api', 'Transaction')
    Transaction.objects.update(transaction_hash='')

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_short_like_comment_view_and_more'),  # Replace with your latest migration
    ]

    operations = [
        migrations.RunPython(
            populate_transaction_hashes,
            reverse_populate_transaction_hashes
        ),
    ]
