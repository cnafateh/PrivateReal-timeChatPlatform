from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ConversationMigrationTests(TransactionTestCase):
    def test_merge_reversed_conversations_without_losing_messages(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes("chat")
        old = [("chat", "0001_initial")]
        executor.migrate(old)
        try:
            apps = executor.loader.project_state(old).apps
            User = apps.get_model("auth", "User")
            Chat = apps.get_model("chat", "PrivateChat")
            Message = apps.get_model("chat", "Message")
            alice = User.objects.create(username="migration-alice")
            bob = User.objects.create(username="migration-bob")
            first = Chat.objects.create(user1=alice, user2=bob)
            second = Chat.objects.create(user1=bob, user2=alice)
            for chat in [first, second]:
                Message.objects.create(chat=chat, sender=alice, receiver=bob, content="Preserve me")
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            apps = executor.loader.project_state(latest).apps
            self.assertEqual(apps.get_model("chat", "PrivateChat").objects.count(), 1)
            rows = apps.get_model("chat", "Message").objects.all()
            self.assertEqual(rows.count(), 2)
            self.assertEqual(set(rows.values_list("chat_id", flat=True)), {first.pk})
        finally:
            MigrationExecutor(connection).migrate(latest)
