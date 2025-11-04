from django.db import models


class Event(models.Model):
    content = models.TextField()
    source = models.CharField(max_length=255, null=True)
    source_id = models.CharField(max_length=255, null=True)
