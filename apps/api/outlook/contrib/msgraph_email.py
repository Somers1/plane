import datetime
from datetime import timedelta
from typing import Any

import requests
from cryptography.utils import cached_property
from dateutil import parser
from django.utils import timezone

from outlook import utils


class MSGraphEmail:
    API = "https://graph.microsoft.com/v1.0/"

    def __init__(
            self,
            mail_folder: str,
            client_id: str,
            client_secret: str,
            tenant_id: str,
            email_address: str,
            timeout: int = 10,
            max_retries: int = 3
    ):
        self.mail_folder_name = mail_folder
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.email_address = email_address
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def token_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    @property
    def token_payload(self) -> dict:
        return {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'https://graph.microsoft.com/.default'
        }

    @utils.retry_with_timeout()
    def get_access_token(self) -> str:
        response = requests.post(
            self.token_url,
            data=self.token_payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()['access_token']

    @property
    def session(self) -> requests.Session:
        headers = {
            "Authorization": f"Bearer {self.get_access_token()}",
            "Content-Type": "application/json",
            "Prefer": 'IdType="ImmutableId"'
        }
        session = requests.Session()
        session.headers.update(headers)
        return session

    @cached_property
    def messages_endpoint(self):
        if self.mail_folder_name:
            return f"{self.API}users/{self.email_address}/mailFolders/{self.mail_folder_name}/messages"
        return f"{self.API}users/{self.email_address}/messages"

    @utils.retry_with_timeout()
    def get_all_emails(self):
        endpoint = self.messages_endpoint
        while True:
            response = self.session.get(endpoint, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            for email in data['value']:
                yield email
            next_link = data.get('@odata.nextLink')
            if not next_link:
                break
            endpoint = next_link

    @utils.retry_with_timeout()
    def get_delta(self, delta_token=None):
        endpoint = f"{self.messages_endpoint}/delta?changeType=created"
        if delta_token:
            endpoint = delta_token
        while True:
            response = self.session.get(endpoint, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            for email in data['value']:
                yield email
            next_link = data.get('@odata.nextLink')
            if not next_link:
                yield data.get('@odata.deltaLink')
                break
            endpoint = next_link


    def by_time_range(self, start_date, end_date=None, limit=None):
        if isinstance(start_date, datetime.datetime):
            start_date = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        if isinstance(end_date, datetime.datetime):
            end_date = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        if not end_date:
            end_date = timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        date_filter = f"ReceivedDateTime ge {start_date} and ReceivedDateTime le {end_date}"
        endpoint = self.messages_endpoint
        params = {
            "$filter": date_filter,
            "$orderby": "ReceivedDateTime asc",
            "$top": "100"  # Process in batches of 100
        }
        while True:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            for email in data['value']:
                yield email
            if '@odata.nextLink' in data:
                endpoint = data['@odata.nextLink']
                params = {}
            else:
                break

    @utils.retry_with_timeout()
    def get_email(self, email_id):
        endpoint = f"{self.API}users/{self.email_address}/messages/{email_id}"
        response = self.session.get(endpoint, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @utils.retry_with_timeout()
    def get_folder(self, folder_id):
        endpoint = f"{self.API}users/{self.email_address}/mailFolders/{folder_id}"
        response = self.session.get(endpoint, timeout=self.timeout)
        response.raise_for_status()
        folder_info = response.json()
        return folder_info

    @utils.retry_with_timeout()
    def find_folder_by_name(self, folder_name, parent_folder_id=None):
        if parent_folder_id:
            endpoint = f"{self.API}users/{self.email_address}/mailFolders/{parent_folder_id}/childFolders"
        else:
            endpoint = f"{self.API}users/{self.email_address}/mailFolders"
        filter_param = f"?$filter=displayName eq '{folder_name}'"
        filtered_endpoint = endpoint + filter_param
        response = self.session.get(filtered_endpoint, timeout=self.timeout)
        response.raise_for_status()
        folders = response.json().get('value', [])
        if folders:
            return folders[0]
        endpoint = f"{endpoint}?$top=999"
        response = self.session.get(endpoint, timeout=self.timeout)
        response.raise_for_status()
        top_folders = response.json().get('value', [])
        for folder in top_folders:
            result = self.find_folder_by_name(folder_name, folder['id'])
            if result:
                return result
        return None

    @utils.retry_with_timeout()
    def list_folders(self, parent_folder_id=None, nested=False):
        if parent_folder_id:
            endpoint = f"{self.API}users/{self.email_address}/mailFolders/{parent_folder_id}/childFolders"
        else:
            endpoint = f"{self.API}users/{self.email_address}/mailFolders"
        endpoint += "?$top=999"
        response = self.session.get(endpoint, timeout=self.timeout)
        response.raise_for_status()
        folders = response.json().get('value', [])
        all_folders = folders.copy()
        if nested:
            for folder in folders:
                child_folders = self.list_folders(folder['id'])
                if child_folders:
                    all_folders.extend(child_folders)
        return all_folders

    @utils.retry_with_timeout()
    def get_emails_batch(self, email_ids):
        batch_requests = []
        for i, email_id in enumerate(email_ids):
            batch_requests.append({
                "id": str(i),
                "method": "GET",
                "url": f"/users/{self.email_address}/messages/{email_id}"
            })
        batch_payload = {
            "requests": batch_requests
        }
        endpoint = f"{self.API}$batch"
        response = self.session.post(endpoint, json=batch_payload, timeout=self.timeout)
        response.raise_for_status()
        batch_response = response.json()
        emails = {}
        for resp in batch_response.get('responses', []):
            if resp.get('status') == 200:
                email = resp.get('body')
                emails[email['id']] = email
        return emails

    @utils.retry_with_timeout()
    def subscribe(self, callback_url, reference) -> tuple[str, Any]:
        expiration = (utils.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M:%SZ')
        if self.mail_folder_name:
            resource = f"users/{self.email_address}/mailFolders/{self.mail_folder_name}/messages"
        else:
            resource = f"users/{self.email_address}/messages"
        subscription_data = {
            "changeType": "created",
            "notificationUrl": callback_url,
            "resource": resource,
            "expirationDateTime": expiration,
            "clientState": str(reference)
        }
        response = self.session.post(
            f"{self.API}subscriptions",
            json=subscription_data,
            timeout=self.timeout,
        )
        response.raise_for_status()
        subscription_details = response.json()
        return (
            subscription_details['id'],
            parser.parse(subscription_details['expirationDateTime'])
        )

    @utils.retry_with_timeout()
    def list_attachments(self, message_id: str):
        endpoint = f"{self.API}users/{self.email_address}/messages/{message_id}/attachments"
        response = self.session.get(endpoint, timeout=self.timeout)
        response.raise_for_status()
        return response.json()['value']

    @utils.retry_with_timeout()
    def get_attachment(self, message_id, attachment_id):
        endpoint = f"{self.API}users/{self.email_address}/messages/{message_id}/attachments/{attachment_id}"
        response = self.session.get(endpoint, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @utils.retry_with_timeout()
    def list_subscriptions(self):
        response = self.session.get(f"{self.API}subscriptions", timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @utils.retry_with_timeout()
    def unsubscribe(self, subscription_id: str):
        return self.session.delete(f"{self.API}subscriptions/{subscription_id}", timeout=self.timeout)

    @utils.retry_with_timeout()
    def forward(self, email_id: str, to_recipient: str):
        endpoint = f"{self.API}users/{self.email_address}/messages/{email_id}/forward"
        payload = {"toRecipients": [{"emailAddress": {"address": to_recipient}}]}
        return self.session.post(endpoint, json=payload, timeout=self.timeout)

    @utils.retry_with_timeout()
    def move(self, email_id: str, folder_id: str):
        endpoint = f"{self.API}users/{self.email_address}/messages/{email_id}/move"
        payload = {"destinationId": folder_id}
        return self.session.post(endpoint, json=payload, timeout=self.timeout)

    @utils.retry_with_timeout()
    def create_draft(self, subject, body, to_recipients, cc_recipients=None, bcc_recipients=None, content_type="Text"):
        endpoint = f"{self.API}users/{self.email_address}/messages"
        payload = {
            "subject": subject,
            "body": {"contentType": content_type, "content": body},
            "toRecipients": [{"emailAddress": {"address": r}} for r in to_recipients],
            "isDraft": True
        }
        if cc_recipients:
            payload["ccRecipients"] = [{"emailAddress": {"address": r}} for r in cc_recipients]
        if bcc_recipients:
            payload["bccRecipients"] = [{"emailAddress": {"address": r}} for r in bcc_recipients]
        response = self.session.post(endpoint, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @utils.retry_with_timeout()
    def update_draft(self, message_id, subject=None, body=None, to_recipients=None, cc_recipients=None,
                     bcc_recipients=None, content_type="Text"):
        endpoint = f"{self.API}users/{self.email_address}/messages/{message_id}"
        payload = {}
        if subject:
            payload["subject"] = subject
        if body:
            payload["body"] = {"contentType": content_type, "content": body}
        if to_recipients:
            payload["toRecipients"] = [{"emailAddress": {"address": r}} for r in to_recipients]
        if cc_recipients:
            payload["ccRecipients"] = [{"emailAddress": {"address": r}} for r in cc_recipients]
        if bcc_recipients:
            payload["bccRecipients"] = [{"emailAddress": {"address": r}} for r in bcc_recipients]
        response = self.session.patch(endpoint, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()