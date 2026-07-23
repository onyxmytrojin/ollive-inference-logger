import uuid

from django.db import models


class Conversation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversations"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversation({self.id})"


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        related_name="messages",
        on_delete=models.CASCADE,
        db_column="conversation_id",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self):
        return f"Message({self.id}, {self.role})"
