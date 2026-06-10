from django.db import models
from django.conf import settings

class CreateCommunity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='communities')
    name = models.CharField(max_length=100)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "communities"

    def __str__(self):
        return self.name

class CommunityMembers(models.Model):
    community = models.ForeignKey(CreateCommunity, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_memberships')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("community", "user")

    def __str__(self):
        return f"{self.user.username} joined {self.community.name}"

class InviteMembers(models.Model):
    community = models.ForeignKey(CreateCommunity, on_delete=models.CASCADE, related_name='invites')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_invites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("community", "user")

    def __str__(self):
        return f"{self.user.username} invited to {self.community.name}"

class CommunityPosts(models.Model):
    community = models.ForeignKey(CreateCommunity, on_delete=models.CASCADE, related_name='posts')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} posted in {self.community.name}"

class LeaderBoard(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leaderboard')
    community = models.ForeignKey(CreateCommunity, on_delete=models.CASCADE, related_name='leaderboard')
    points = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} in {self.community.name}"


class JoinRequest(models.Model):
    community = models.ForeignKey(CreateCommunity, on_delete=models.CASCADE, related_name='join_requests')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='join_requests')
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('approved', 'Approved'), ('declined', 'Declined')],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("community", "user")

    def __str__(self):
        return f"{self.user.username} request to join {self.community.name} ({self.status})"
    
