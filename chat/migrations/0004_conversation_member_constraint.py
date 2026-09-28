from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chat", "0003_normalize_conversations")]
    operations = [
        migrations.AddConstraint(
            model_name='privatechat',
            constraint=models.CheckConstraint(condition=models.Q(('user1__lt', models.F('user2'))), name='chat_ordered_members'),
        ),
    ]
