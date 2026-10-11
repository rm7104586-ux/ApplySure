
from django.db import models


class DocumentComparison(models.Model):
    document1_name = models.CharField(max_length=255)
    document2_name = models.CharField(max_length=255)

    count_first = models.PositiveIntegerField(default=0)
    count_second = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.document1_name} vs {self.document2_name}"
