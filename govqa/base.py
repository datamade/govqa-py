"""
https://stackoverflow.com/questions/54927385/scrape-aspx-form-with-python
"""
import re

import lxml.html
from scrapelib import Scraper


class GovQA(Scraper):
	"""
	ENDPOINTS = {
		"home": "SupportHome.aspx",
		"login": "Login.aspx",
		"create_account": "CustomerDetails.aspx"
	}
	"""

	def __init__(self, domain, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.domain = domain

		response = self.get(
			self.get_full_url("SupportHome.aspx", session_token="initial request")
		)

		self.session_token = re.search(
			r"^.*\(S\((?P<session_id>.*)\){2}.*$", response.url
		).group("session_id")

	def get_full_url(self, endpoint, session_token=None):
		"""
		S(hash) is an auto-generated session id – you can start with whatever in S(foo) and
		it will redirect to a valid session id.
		"""
		return f"{self.domain}/WEBAPP/_rs/(S({session_token if session_token else self.session_token}))/{endpoint}"

	def create_account(self):
		...

	def login(self, username, password):
		login_page = self.get_full_url("Login.aspx")
		response = self.get(login_page)

		# Scrape state values
		tree = lxml.html.fromstring(response.text)

		viewstate = tree.xpath("//input[@id='__VIEWSTATE']")[0].value
		viewstategenerator = tree.xpath("//input[@id='__VIEWSTATEGENERATOR']")[
            0
        ].value

		return self.post(
			self.get_full_url(login_page),
			data={
				"__VIEWSTATE": viewstate,
				"__VIEWSTATEGENERATOR": viewstategenerator,
				"ASPxFormLayout1$txtUsername": username,
				"ASPxFormLayout1$txtPassword:": password,
				"ASPxFormLayout1$btnLogin": "Submit"
			}
		)

	def request(self, *args, **kwargs):
		response = super().request(*args, **kwargs)

		if "There was a problem serving the requested page" in response.text:
			response.status_code = 500

		elif "Page Temporarily Unavailable" in response.text:
			response.status_code = 500

		return response

	def reset_password(self):
		...

	def submit_request(self):
		...

	def submit_request_attachments(self):
		...

	def retrieve_message(self):
		...

	def send_message(self):
		...

	def retrieve_request_response(self):
		...
