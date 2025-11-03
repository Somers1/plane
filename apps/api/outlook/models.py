import asyncio
import base64
import io
import logging
from datetime import timedelta
from functools import cached_property
from pathlib import Path

import pdfplumber
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone
from django_cryptography.fields import encrypt
from pdfminer.pdfdocument import PDFPasswordIncorrect
from pgvector.django import VectorField

from bedrock.bedrock_sdk.converse import InvalidFormat
from bedrock.models import llm
from outlook import utils
from outlook.contrib.msgraph_email import MSGraphEmail

logger = logging.getLogger(__name__)


class EmailDataSource(models.Model):
    email_address = models.EmailField()
    client_id = models.CharField(max_length=255)
    client_secret = encrypt(models.CharField(max_length=255, null=True, blank=True))
    tenant_id = models.CharField(max_length=255, null=True, blank=True)
    mail_folder = models.CharField(max_length=255, null=True, blank=True)
    folder_display_name = models.CharField(max_length=255, null=True, blank=True)
    delta_token = models.TextField(null=True, blank=True)
    subscription_id = models.CharField(max_length=255, null=True, blank=True)
    subscription_callback = models.URLField(null=True, blank=True)
    subscription_expiry = models.DateTimeField(null=True, blank=True)
    last_sync = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    @cached_property
    def msgraph_client(self):
        return MSGraphEmail(
            mail_folder=self.mail_folder,
            client_id=self.client_id,
            client_secret=self.client_secret,
            tenant_id=self.tenant_id,
            email_address=self.email_address
        )

    def ms_client_sub_folders(self):
        return self.msgraph_client.list_folders(self.mail_folder)

    def subscribe(self):
        self.subscription_id, self.subscription_expiry = self.msgraph_client.subscribe(
            self.subscription_callback, reference=self.id)
        self.save(update_fields=['subscription_id', 'subscription_expiry'])

    def unsubscribe(self):
        self.msgraph_client.unsubscribe(self.subscription_id)

    def resubscribe(self):
        self.unsubscribe()
        self.subscribe()

    def check_renew_subscription(self):
        if not (self.subscription_id and self.subscription_expiry):
            return self.subscribe()
        if self.subscription_expiry and self.subscription_expiry < timezone.now() + timedelta(days=1):
            return self.resubscribe()
        return None

    def scrape_delta(self):
        return self.save_emails(self.msgraph_client.get_delta(self.delta_token))

    def scrape_all(self):
        return self.save_emails(self.msgraph_client.get_all_emails())

    def scrape_range(self, start_time, end_time=None):
        return self.save_emails(self.msgraph_client.by_time_range(start_time, end_time))

    def save_emails(self, email_generator, batch_size=100):
        emails = []
        self.last_sync = timezone.now()
        for email in email_generator:
            if isinstance(email, str):
                self.delta_token = email
                break
            emails.append(Email(source=self).from_msgraph(email))
            if len(emails) >= batch_size:
                self.create_emails(emails)
                logging.info(f'Scraped {len(emails)} emails')
                emails = []
        self.create_emails(emails)
        logging.info(f'Scraped {len(emails)} emails')
        self.save(update_fields=['delta_token', 'last_sync'])

    def create_emails(self, emails):
        self.emails.bulk_create(emails, ignore_conflicts=True)

    @cached_property
    def ms_graph_folder_id(self):
        return self.msgraph_client.get_folder(self.mail_folder)['id']


class EmbeddingHandler(models.Manager):
    def embed_missing(self):
        emails = list(self.filter(embedding__isnull=True))
        batch_size = 20
        total_batches = (len(emails) + batch_size - 1) // batch_size
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            texts = []
            valid_emails = []
            for email in batch:
                if email.cleaned_body:
                    texts.append(email.email_prompt)
                    valid_emails.append(email)
            if not texts:
                continue
            batch_num = i // batch_size + 1
            print(f"Processing batch {batch_num}/{total_batches}: {len(texts)} emails")
            response = llm.embed.embed_documents(texts)
            embeddings = response.embeddings['float']
            for email, embedding in zip(valid_emails, embeddings):
                email.embedding = embedding
            Email.objects.bulk_update(valid_emails, ['embedding'])

class Email(models.Model):
    source = models.ForeignKey(EmailDataSource, on_delete=models.CASCADE, related_name='emails')
    message_id = models.CharField(max_length=255)
    conversation_id = models.TextField(blank=True)
    received_datetime = models.DateTimeField()
    recipients = ArrayField(base_field=models.TextField(), null=True)
    subject = models.TextField(blank=True)
    from_email = models.EmailField()
    body = models.TextField()
    has_attachments = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    cleaned_body = models.TextField(null=True)
    embedding = VectorField(dimensions=1536, null=True)

    objects = models.Manager()
    embeddings = EmbeddingHandler()

    class Meta:
        unique_together = ('source', 'message_id')
        indexes = [
            models.Index(fields=['conversation_id'], name='conversation_id_idx'),
            models.Index(fields=['-received_datetime'], name='received_datetime_desc_idx')
        ]

    def __str__(self):
        return f'{self.received_datetime} {self.subject}'

    def from_msgraph(self, email):
        self.message_id = email['id']
        self.conversation_id = email['conversationId']
        self.received_datetime = email['receivedDateTime']
        self.recipients = [r['emailAddress']['address'] for r in email['toRecipients']]
        self.subject = email['subject'] or ''
        self.from_email = email['from']['emailAddress']['address']
        self.body = email['body']['content']
        self.has_attachments = email['hasAttachments']
        return self

    @property
    def from_and_to_string(self):
        return f'From: {self.from_email}, To: {self.recipients}'

    @property
    def email_prompt(self):
        return f"From: {self.from_email}\nSubject: {self.subject}\n\n{self.ensured_cleaned_body()}"

    def get_ms_graph_attachments(self, include_inline=False):
        if not self.has_attachments:
            return []
        if include_inline:
            return self.source.msgraph_client.list_attachments(self.message_id)
        return [a for a in self.source.msgraph_client.list_attachments(self.message_id) if not a['isInline']]

    def get_attachments(self, include_inline=False):
        if self.has_attachments and not self.attachments.exists():
            try:
                self.save_attachments()
            except Exception as e:
                logger.error(f'Failed to save attachments for {self.id} to prompt: {e}')
        if include_inline:
            return self.attachments.all()
        return self.attachments.filter(inline=False)

    def add_attachments_to_prompt(self, prompt):
        for attachment in self.get_attachments():
            try:
                attachment.add_to_prompt(prompt)
            except Exception as e:
                logger.error(f'Failed to add attachment {attachment.id} to prompt: {e}')

    def age_on_received(self):
        return (self.created_at - self.received_datetime).total_seconds()

    def is_in_source_folder(self):
        try:
            return self.source.ms_graph_folder_id == self.get_current_folder_id()
        except Exception as e:
            logger.error(e)
            return False

    def ensured_cleaned_body(self):
        if not self.cleaned_body:
            self.update_cleaned_body()
        return self.cleaned_body

    def update_cleaned_body(self, autosave=True):
        self.cleaned_body = utils.clean_html(self.body)
        if autosave:
            self.save(update_fields=['cleaned_body'])
        return self

    def handle(self, skip_attachments=False):
        if self.embedding is None:
            self.embed()
        if self.has_attachments and not skip_attachments:
            self.save_attachments()

    def save_attachments(self):
        for attachment in self.get_ms_graph_attachments(include_inline=True):
            new_attachment, _ = self.attachments.get_or_create(
                name=attachment['name'],
                attachment_id=attachment['id'],
                content_type=attachment['contentType'],
                inline=attachment['isInline'],
                size=attachment['size'],
                email=self
            )
            new_attachment.store_text_content()

    def embed(self):
        if not self.email_prompt.strip('\n').strip():
            return self
        self.embedding = llm.embed.embed_documents([self.email_prompt])
        self.save(update_fields=['embedding'])
        return self

    def get_current_folder_id(self):
        return self.get_ms_graph_email()['parentFolderId']

    def get_ms_graph_email(self):
        return self.source.msgraph_client.get_email(self.message_id)

    def conversation_emails(self):
        return Email.objects.filter(conversation_id=self.conversation_id)


class Attachment(models.Model):
    email = models.ForeignKey(Email, on_delete=models.CASCADE, related_name='attachments')
    name = models.CharField(max_length=255)
    attachment_id = models.CharField(max_length=255, null=True)
    content_type = models.CharField(max_length=255, null=True)
    inline = models.BooleanField(null=True)
    size = models.IntegerField(null=True)
    processed_sharepoint_link = models.TextField(null=True)
    text_content = models.TextField(null=True)

    def __str__(self):
        return f'{self.name} - {self.content_type} - {self.size_mb}'

    @cached_property
    def content(self):
        try:
            return self.email.source.msgraph_client.get_attachment(
                self.email.message_id, self.attachment_id)['contentBytes']
        except Exception as e:
            if '404' in str(e):
                self.text_content = 'Failed to load attachment due to 404 not found.'
                self.save(update_fields=['text_content'])
            return logger.error(f'Failed to get attachment for {self.id}: {e}')

    @cached_property
    def decoded_content(self):
        return base64.b64decode(self.content)

    @property
    def file_type(self):
        return self.name.split('.')[-1].lower()

    def is_image(self):
        return self.file_type in ["png", "jpeg", "gif", "webp"]

    def store_text_content(self):
        try:
            self.text_content = self.parse_text()
            if self.text_content:
                self.text_content = self.text_content.replace('\x00', '')
                self.save(update_fields=['text_content'])
            return self.text_content
        except Exception as e:
            logger.error(f'Failed to save text content to database: {e}')
            return self.text_content

    def parse_text(self):
        if self.file_type == 'pdf':
            if not self.content:
                return None
            try:
                with pdfplumber.open(io.BytesIO(self.decoded_content)) as pdf:
                    text = ""
                    for page in pdf.pages:
                        text += page.extract_text() + "\n"
                return text.strip('\n').strip()
            except Exception as e:
                if hasattr(e, 'args') and e.args:
                    if isinstance(e.args[0], PDFPasswordIncorrect):
                        return 'This is a password protected document and cannot be read'
                logger.error(e, exc_info=True)
                return None
        return None

    def get_text(self):
        if self.text_content is not None:
            return self.text_content
        return self.store_text_content()

    @property
    def size_mb(self):
        return self.size / 1024 / 1024

    def add_to_prompt(self, prompt):
        if text := self.get_text():
            prompt.add_text(f'File name: {self.name}\n<file_content>{text}</file_content>')
            return True
        if not self.content:
            return False
        if self.size < 4 * 1024 * 1024:
            try:
                prompt.add_document(self.decoded_content, self.name)
                return True
            except InvalidFormat:
                try:
                    prompt.add_image(self.decoded_content, self.file_type)
                    return True
                except InvalidFormat:
                    return False
        if text := self.get_text():
            prompt.add_text(text)
            return True
        return False

    @property
    def suffix(self):
        return Path(self.name).suffix
