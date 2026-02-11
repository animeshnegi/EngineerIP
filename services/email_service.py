
import re
import logging
from flask import current_app, render_template_string
import requests

class EmailService:
    def __init__(self):
        self.base_url = current_app.config['BASE_URL']
        self.api_key = current_app.config['API_KEY']
        self.default_sender = "Mike@engineer-ip.com"
        self.logger = logging.getLogger(__name__)

    def _sanitize_input(self, text):
        """Sanitize user input to prevent XSS"""
        return re.sub(r'[<>]', '', text).strip()

    def _send_email_via_api(self, payload):
        """Core method to handle API communication"""
        try:
            response = requests.post(
                self.base_url,
                data=payload,
                timeout=10  # Add timeout for request safety
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Email API Error: {str(e)}")
            return False

    def send_query_notification(self, query_data):
        """
        Send notification about new query to admin
        query_data should contain: name, email, subject, message, srno
        """
        # Sanitize all user inputs
        sanitized_data = {
            key: self._sanitize_input(value)
            for key, value in query_data.items()
        }

        # Render email template
        email_body = render_template_string('''
<table align="center" cellpadding="1" cellspacing="1" style="width:80%;">
	<tbody>
		<tr>
			<td colspan="2" style="text-align: center;"><strong><span style="font-size:20px;"><em><span style="font-family:Times New Roman,Times,serif;">&nbsp;</span></em></span><span style="font-size:22px;"><em><span style="font-family:Times New Roman,Times,serif;">Engineer</span></em></span><span style="font-size:28px;"><span style="color:#e67e22;"><span style="font-family:Times New Roman,Times,serif;"><em>IP</em></span></span></span></strong></td>
		</tr>
		<tr>
			<td colspan="2" style="vertical-align: middle; text-align: center;"><span style="font-size:14px;">Received&nbsp;New&nbsp;WebSite query Number#&nbsp;<strong>&nbsp;{{srno}}&nbsp;</strong></span></td>
		</tr>
	</tbody>
</table>

<p>&nbsp;</p>

<table align="center" border="1" bordercolor="#ccc" cellpadding="5" cellspacing="0" style="border-collapse:collapse;width:80%;">
	<tbody>
		<tr>
			<td style="width: 20%; vertical-align: top;"><strong>Name:</strong></td>
			<td>{{name}}</td>
		</tr>
		<tr>
			<td style="vertical-align: top;"><strong>Email:</strong></td>
			<td>{{email}}</td>
		</tr>
		<tr>
			<td style="vertical-align: top;"><strong>Subject:</strong></td>
			<td>{{subject}}</td>
		</tr>
		<tr>
			<td style="vertical-align: top;"><strong>Message:</strong></td>
			<td><em>{{message}}</em></td>
		</tr>
	</tbody>
</table>
        ''', **sanitized_data)

        payload = {
            "apikey": self.api_key,
            "subject": f"New Query Received (ID: {sanitized_data['srno']})",
            "from": self.default_sender,
            "to": ["negi.animesh5@gmail.com", "mail@engineerip.com","ad@solutionengineer.in"],
            "bodyHtml": email_body,
            "isTransactional": True
        }

        return self._send_email_via_api(payload)

    # Add other email methods (campaign emails, etc) here