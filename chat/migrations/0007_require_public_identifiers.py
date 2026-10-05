import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chat", "0006_populate_public_identifiers")]
    operations = [
        migrations.AlterField(model_name=name, name="public_id",
                              field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True))
        for name in ("message", "privatechat")
    ]
