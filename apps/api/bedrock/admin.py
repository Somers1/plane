from django.contrib import admin
from . import models


class PromptAdmin(admin.ModelAdmin):
    list_display = ('name', 'prompt')
    search_fields = ('name', 'prompt')


admin.site.register(models.Prompt, PromptAdmin)
