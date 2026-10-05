import uuid
from django.db import migrations


def populate(apps, schema_editor):
    alias = schema_editor.connection.alias
    for name in ("Message", "PrivateChat"):
        Model = apps.get_model("chat", name)
        for pk in Model.objects.using(alias).filter(public_id__isnull=True).values_list("pk", flat=True).iterator():
            Model.objects.using(alias).filter(pk=pk).update(public_id=uuid.uuid4())
    User = apps.get_model("auth", "User")
    Profile = apps.get_model("chat", "Profile")
    for pk in User.objects.using(alias).values_list("pk", flat=True).iterator():
        Profile.objects.using(alias).get_or_create(user_id=pk, defaults={"public_id": uuid.uuid4()})


class Migration(migrations.Migration):
    dependencies = [("chat", "0005_message_public_id_privatechat_public_id_profile")]
    operations = [migrations.RunPython(populate, migrations.RunPython.noop)]
