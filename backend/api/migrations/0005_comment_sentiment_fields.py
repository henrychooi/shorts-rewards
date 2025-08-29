# Generated manually for comment sentiment analysis fields

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_short_audio_processed_at_short_audio_quality_score_and_more'),
    ]

    operations = [
        # Add comment analysis fields to Short model
        migrations.AddField(
            model_name='short',
            name='comment_analysis_score',
            field=models.FloatField(blank=True, help_text='Aggregated comment sentiment score (-1 to 1)', null=True),
        ),

        # Add comment analysis fields to Comment model
        migrations.AddField(
            model_name='comment',
            name='sentiment_score',
            field=models.FloatField(blank=True, help_text='Sentiment score (-1 to 1)', null=True),
        ),
        migrations.AddField(
            model_name='comment',
            name='sentiment_label',
            field=models.CharField(blank=True, help_text='Sentiment label (positive/negative/neutral)', max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='comment',
            name='analyzed_at',
            field=models.DateTimeField(blank=True, help_text='When sentiment analysis was performed', null=True),
        ),
    ]
