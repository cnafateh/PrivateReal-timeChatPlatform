from django.db import migrations

def normalize_members(apps, schema_editor):
    Chat = apps.get_model("chat", "PrivateChat")
    Message = apps.get_model("chat", "Message")
    alias = schema_editor.connection.alias
    for chat in Chat.objects.using(alias).all().iterator():
        if chat.user1_id == chat.user2_id:
            raise RuntimeError("Resolve self-conversations before migrating.")
        if chat.user1_id > chat.user2_id:
            existing = Chat.objects.using(alias).filter(user1_id=chat.user2_id, user2_id=chat.user1_id).first()
            if existing:
                Message.objects.using(alias).filter(chat_id=chat.pk).update(chat_id=existing.pk)
                chat.delete(using=alias)
            else:
                chat.user1_id, chat.user2_id = chat.user2_id, chat.user1_id
                chat.save(using=alias, update_fields=["user1", "user2"])


class Migration(migrations.Migration):
    dependencies = [("chat", "0002_alter_message_options_message_attachment_and_more")]
    operations = [migrations.RunPython(normalize_members, migrations.RunPython.noop)]
