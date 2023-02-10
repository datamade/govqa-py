"""
https://stackoverflow.com/questions/54927385/scrape-aspx-form-with-python
"""
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

    @property
    def BASE_HEADERS(self):
        return {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:12.0) Gecko/20100101 Firefox/12.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip, deflate",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        }

    def __init__(self, domain, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.domain = domain

        # Generate a 25-character hash to use as a token for this session
        self.session_token = md5(
            datetime.now().isoformat().encode()
        ).hexdigest()[:24]

    def request(self, *args, **kwargs):
        response = super().request(*args, **kwargs)

        if "There was a problem serving the requested page" in response.text:
            response.status_code = 500

        elif "Page Temporarily Unavailable" in response.text:
            response.status_code = 500

        return response

    def get_full_url(self, endpoint):
        return f"{self.domain}/WEBAPP/_rs/(S({self.session_token}))/{endpoint}"

    def create_account(self):
        ...

    def login(self, username, password):
        # TODO: Add base headers in request method
        login_headers = self.BASE_HEADERS.copy()
        login_headers["Referer"] = self.get_full_url("SupportHome.aspx")

        login_url = self.get_full_url("Login.aspx")

        response = self.get(
            login_url,
            headers=login_headers
        )

        tree = lxml.html.fromstring(response.text)

        # TODO: Get sSessionID?

        viewstate = tree.xpath("//input[@id='__VIEWSTATE']")[0].value
        viewstategenerator = tree.xpath("//input[@id='__VIEWSTATEGENERATOR']")[
            0
        ].value
        request_verification_token =  tree.xpath("//input[@name='__RequestVerificationToken']")[0].value

        login_headers["Referer"] = login_url
        login_headers["Content-Type"] = "application/x-www-form-urlencoded"

        # TODO: Add cookie?

        payload = {
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": viewstategenerator,
            "__EVENTTARGET": None,
            "__EVENTARGUMENT": None,
            "__RequestVerificationToken": request_verification_token,
            "ASPxFormLayout1$txtUsername": username,
            "ASPxFormLayout1$txtPassword:": password,
            "ASPxFormLayout1$btnLogin": "Submit",
        }

        return client.post(
            login_url,
            headers=login_headers,
            data=payload,
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

    import pdb
    pdb.set_trace()
