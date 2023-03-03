from datetime import datetime
from hashlib import md5
import os
import re

import lxml.html
from scrapelib import Scraper


class GovQA(Scraper):
    """
    ENDPOINTS = {
        "home": "SupportHome.aspx",
        "login": "Login.aspx",
        "create_account": "CustomerDetails.aspx"
        "logged_in_home": "CustomerHome.aspx",
    }
    """

    def __init__(self, domain, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.domain = domain

    def request(self, *args, **kwargs):
        response = super().request(*args, **kwargs)

        if "There was a problem serving the requested page" in response.text:
            response.status_code = 500

        elif "Page Temporarily Unavailable" in response.text:
            response.status_code = 500

        return response

    def url_from_endpoint(self, endpoint):
        return f"{self.domain}/WEBAPP/_rs/{endpoint}"

    def create_account(self):
        ...

    def login(self, username, password):
        headers = {
            "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Mobile Safari/537.36",
        }

        response = self.get(
            self.url_from_endpoint("Login.aspx"),
            headers=login_headers,
            allow_redirects=True,
        )

        tree = lxml.html.fromstring(response.text)

        viewstate = tree.xpath("//input[@id='__VIEWSTATE']")[0].value
        viewstategenerator = tree.xpath("//input[@id='__VIEWSTATEGENERATOR']")[
            0
        ].value
        request_verification_token =  tree.xpath("//input[@name='__RequestVerificationToken']")[0].value

        headers["content-type"] = "application/x-www-form-urlencoded"

        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate,
            "__RequestVerificationToken": request_verification_token,
            "ASPxFormLayout1$txtUsername": username,
            "ASPxFormLayout1$txtPassword": password,
            "ASPxFormLayout1$btnLogin": "Submit",
            "__VIEWSTATEGENERATOR": viewstategenerator,
            "__VIEWSTATEENCRYPTED": "",
        }

        return self.post(
            response.url,
            data=payload,
            headers=headers,
            allow_redirects=True
        )

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


if __name__ == "__main__":
    client = GovQA(os.environ["GOVQA_DOMAIN"])

    response = client.login(os.environ["GOVQA_USERNAME"], os.environ["GOVQA_PASSWORD"])

    with open("response.html", "w") as initial_response_content:
        initial_response_content.write(response.content.decode("utf-8"))
