from datetime import datetime
from hashlib import md5
import os
import re

import lxml.html
from scrapelib import Scraper
from urllib.parse import urlparse, parse_qs


class GovQA(Scraper):
    """
    ENDPOINTS = {
        "home": "SupportHome.aspx",
        "login": "Login.aspx",
        "create_account": "CustomerDetails.aspx"
        "logged_in_home": "CustomerHome.aspx",
        "messages": "CustomerIssues.aspx",
        "message": "RequestEdit.aspx",
    }
    """

    def __init__(self, domain, username, password, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.domain = domain
        self.username = username
        self.password = password

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

    def login(self):
        headers = {
            "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Mobile Safari/537.36",
        }

        response = self.get(
            self.url_from_endpoint("Login.aspx"),
            headers=headers,
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
            "ASPxFormLayout1$txtUsername": self.username,
            "ASPxFormLayout1$txtPassword": self.password,
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
        """
        Text and attachments
        """
        ...

    def update_request(self, request_id):
        ...

    def list_requests(self):
        self.login()

        response = self.get(
            self.url_from_endpoint("CustomerIssues.aspx"),
        )

        tree = lxml.html.fromstring(response.text)

        request_links = tree.xpath("//a[contains(@id, 'referenceLnk')]")

        requests = []

        for link in request_links:
            requests.append({
                "id": parse_qs(urlparse(link.attrib["href"]).query)["rid"][0],
                "reference_number": link.text,
                "status": link.xpath(
                    "//ancestor::div[@class='innerlist']/descendant::div[starts-with(@class, 'list_status')]/text()"
                )[0],
            })

        return requests

    def get_request(self, request_id):
        self.login()

        response = self.get(
            self.url_from_endpoint("RequestEdit.aspx"),
            params={"rid": request_id}
        )

        tree = lxml.html.fromstring(response.text)

        request = {
            "id": request_id,
            "request_type": tree.xpath("//span[@id='RequestEditFormLayout_roType']/text()")[0],
            "contact_email": tree.xpath("//span[@id='RequestEditFormLayout_roContactEmail']/text()")[0],
            "reference_number": tree.xpath("//span[@id='RequestEditFormLayout_roReferenceNo']/text()")[0],
            "messages": [],
        }

        for message in tree.xpath("//table[contains(@id, 'rptMessageHistory')]"):
            sender, = message.xpath(".//span[contains(@class, 'dxrpHT')]/text()")

            parsed_sender = re.match(
                r"^ On (?P<date>\d{1,2}\/\d{1,2}\/\d{4}) (?P<time>\d{1,2}:\d{1,2}:\d{1,2} (A|P)M), (?P<name>.*) wrote:$",
                sender
            )

            body = message.xpath(".//div[contains(@class, 'dxrpCW')]/text()") + message.xpath(".//div[contains(@class, 'dxrpCW')]/descendant::*/text()")

            request["messages"].append({
                "id": message.attrib["id"].split("_")[-1],
                "sender": parsed_sender.group("name"),
                "date": parsed_sender.group("date"),
                "time": parsed_sender.group("time"),
                "body": re.sub(r"\s+", " ", " ".join(body)).strip(),
            })

        return request

    def get_request_attachments(self):
        """
        Should this be separate?
        """
        ...


if __name__ == "__main__":
    client = GovQA(
        os.environ["GOVQA_DOMAIN"],
        os.environ["GOVQA_USERNAME"],
        os.environ["GOVQA_PASSWORD"],
    )

    response = client.list_requests()

    import pprint
    pprint.pprint(response)

    response = client.get_request(response[0]["id"])

    pprint.pprint(response)
