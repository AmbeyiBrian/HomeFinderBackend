# Generated by Django 5.1.4 on 2025-03-05 13:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_mpesatransaction_checkout_request_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='mpesatransaction',
            name='merchant_request_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
