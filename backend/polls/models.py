from django.conf import settings
from django.db import models
from django.db.models import Q


class Poll(models.Model):
    question = models.CharField(max_length=200)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.question


class Option(models.Model):
    poll = models.ForeignKey(Poll, related_name="options", on_delete=models.CASCADE)
    text = models.CharField(max_length=100)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.text


class Vote(models.Model):
    option = models.ForeignKey(Option, related_name="votes", on_delete=models.CASCADE)
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    voter_key = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["poll", "user"],
                condition=Q(user__isnull=False),
                name="unique_vote_poll_user",
            ),
            models.UniqueConstraint(
                fields=["poll", "voter_key"],
                condition=Q(voter_key__isnull=False),
                name="unique_vote_poll_voter_key",
            ),
            models.CheckConstraint(
                condition=Q(user__isnull=False) | Q(voter_key__isnull=False),
                name="vote_has_user_or_voter_key",
            ),
        ]
