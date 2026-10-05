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
            self.assertEqual(len(set(rows.values_list("public_id", flat=True))), 2)
            self.assertNotIn(None, rows.values_list("public_id", flat=True))
            Profile = apps.get_model("chat", "Profile")
            self.assertEqual(Profile.objects.filter(user_id__in=[alice.pk, bob.pk]).count(), 2)
            self.assertEqual(set(rows.values_list("chat_id", flat=True)), {first.pk})
        finally:
            MigrationExecutor(connection).migrate(latest)


    def test_public_ids_preserve_existing_files_and_multiple_conversations(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes("chat")
        old = [("chat", "0004_conversation_member_constraint")]
        executor.migrate(old)
        try:
            apps = executor.loader.project_state(old).apps
            User = apps.get_model("auth", "User")
            Chat = apps.get_model("chat", "PrivateChat")
            Message = apps.get_model("chat", "Message")
            users = [User.objects.create(username=f"legacy-{i}") for i in range(3)]
            for index, receiver in enumerate(users[1:]):
                chat = Chat.objects.create(user1=users[0], user2=receiver)
                Message.objects.create(chat=chat, sender=users[0], receiver=receiver, content="caption",
                                       attachment=f"attachments/old/{index}", original_name=f"photo-{index}.png")
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            apps = executor.loader.project_state(latest).apps
            for name in ("PrivateChat", "Message"):
                ids = list(apps.get_model("chat", name).objects.values_list("public_id", flat=True))
                self.assertEqual(len(ids), 2)
                self.assertEqual(len(set(ids)), 2)
                self.assertTrue(all(value.version == 4 for value in ids))
            self.assertEqual(set(apps.get_model("chat", "Message").objects.values_list("attachment", flat=True)),
                             {"attachments/old/0", "attachments/old/1"})
            self.assertEqual(apps.get_model("chat", "Profile").objects.count(), 3)
        finally:
            MigrationExecutor(connection).migrate(latest)
