import ast
import io
import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import jsonschema
import lxml.html
import scrapelib

from .input_types import CheckBox, ComboBox, Input, RadioGroup, TextArea, Captcha


class UnauthenticatedError(RuntimeError):
    def __init__(self):
        # Call the base class constructor with the parameters it needs
        super().__init__(
            "This method requires authentication, please run the `login` method before calling this method"
        )


class FormValidationError(RuntimeError):
    pass


class IncorrectCaptcha(FormValidationError):
    pass


class EmailAlreadyExists(FormValidationError):
    pass


class GovQA(scrapelib.Scraper):
    """
    Client for programmatically interacting with GovQA instances.

    :param domain: Root domain of the GovQA instance to interact with, e.g.,
        https://governorny.govqa.us
    :type domain: str
    :param username: GovQA username
    :type username: str
    :param password: GovQA password
    :type password: str
    """

    # do i need this, i don't think so.
    ENDPOINTS = {
        "home": "SupportHome.aspx",
        "login": "Login.aspx",
        "create_account": "CustomerDetails.aspx",
        "logged_in_home": "CustomerHome.aspx",
        "messages": "CustomerIssues.aspx",
        "message": "RequestEdit.aspx",
    }

    def __init__(self, domain, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.domain = domain.rstrip("/")

        self.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/111.0",
            }
        )

    def request(self, *args, **kwargs):
        response = super().request(*args, **kwargs)

        if "There was a problem serving the requested page" in response.text:
            response.status_code = 500
            raise scrapelib.HTTPError(response)

        elif "Page Temporarily Unavailable" in response.text:
            response.status_code = 503
            raise scrapelib.HTTPError(response)

        return response

    def url_from_endpoint(self, endpoint):
        return f"{self.domain}/WEBAPP/_rs/{endpoint}"

    def new_account_form(self):
        return CreateAccountForm(self)

    def request_form(self, request_type):
        return RequestForm(self, request_type)

    def login(self, username, password):
        response = self.get(
            self.url_from_endpoint("Login.aspx"),
            allow_redirects=True,
        )

        tree = lxml.html.fromstring(response.text)

        payload = self._secrets(tree, response)
        payload.update(
            {
                "ASPxFormLayout1$txtUsername": username,
                "ASPxFormLayout1$txtPassword": password,
                "ASPxFormLayout1$btnLogin": "Submit",
            }
        )

        return self.post(response.url, data=payload, allow_redirects=True)

    def _secrets(self, tree, response):
        viewstate = tree.xpath("//input[@id='__VIEWSTATE']")[0].value

        viewstategenerator = tree.xpath("//input[@id='__VIEWSTATEGENERATOR']")[0].value
        request_verification_token = tree.xpath(
            "//input[@name='__RequestVerificationToken']"
        )[0].value

        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate,
            "__RequestVerificationToken": request_verification_token,
            "__VIEWSTATEGENERATOR": viewstategenerator,
            "__VIEWSTATEENCRYPTED": "",
        }

        fieldcounts = tree.xpath("//input[@id='__VIEWSTATEFIELDCOUNT']")
        if fieldcounts:
            viewstatefieldcount = int(fieldcounts[0].value)
            for higher_viewstate in range(1, viewstatefieldcount):
                viewstate = tree.xpath(f"//input[@id='__VIEWSTATE{higher_viewstate}']")[
                    0
                ].value
                payload[f"__VIEWSTATE{higher_viewstate}"] = viewstate

                payload["__VIEWSTATEFIELDCOUNT"] = str(viewstatefieldcount)

        return payload

    def reset_password(self):
        ...

    def update_request(self, request_id):
        ...

    def list_requests(self):
        """
        Retrieve the id, reference number, and status of each request
        submitted by the authenticated account.

        :return: List of dictionaries, each containing the id,
            reference number, and status of all requests.
        :rtype: list

        """

        response = self.get(
            self.url_from_endpoint("CustomerIssues.aspx"),
        )

        self._check_logged_in(response)

        tree = lxml.html.fromstring(response.text)

        request_links = tree.xpath("//a[contains(@id, 'referenceLnk')]")

        requests = []

        for link in request_links:
            requests.append(
                {
                    "id": parse_qs(urlparse(link.attrib["href"]).query)["rid"][0],
                    "reference_number": link.text,
                    "status": link.xpath(
                        "//ancestor::div[@class='innerlist']/descendant::div[starts-with(@class, 'list_status')]/text()"
                    )[0],
                }
            )

        return requests

    def get_request(self, request_id):
        """
        Retrieve detailed information, included messages and
        attachments, about a request.

        :param request_id: Identifier of the request, i.e., the "id"
            from a request dictionary returned by
            list_requests(). N.b., the reference number is not the
            identifier.
        :type request_id: int
        :return: Dictionary of request metadata, correspondence, and
            attachments.
        :rtype: dict

        """

        response = self.get(
            self.url_from_endpoint("RequestEdit.aspx"), params={"rid": request_id}
        )

        self._check_logged_in(response)

        tree = lxml.html.fromstring(response.text)

        request = {
            "id": request_id,
            "request_type": tree.xpath(
                "//span[@id='RequestEditFormLayout_roType']/text()"
            )[0],
            "contact_email": tree.xpath(
                "//span[@id='RequestEditFormLayout_roContactEmail']/text()"
            )[0],
            "reference_number": tree.xpath(
                "//span[@id='RequestEditFormLayout_roReferenceNo']/text()"
            )[0],
            "messages": [],
            "attachments": [],
        }

        for message in tree.xpath("//table[contains(@id, 'rptMessageHistory')]"):
            (sender,) = message.xpath(".//span[contains(@class, 'dxrpHT')]/text()")

            parsed_sender = re.match(
                r"^ On (?P<date>\d{1,2}\/\d{1,2}\/\d{4}) (?P<time>\d{1,2}:\d{1,2}:\d{1,2} (A|P)M), (?P<name>.*) wrote:$",
                sender,
            )

            body = message.xpath(
                ".//div[contains(@class, 'dxrpCW')]/text()"
            ) + message.xpath(".//div[contains(@class, 'dxrpCW')]/descendant::*/text()")

            if "Click Here to View Entire Message" in body:
                (link,) = message.xpath(".//div[contains(@class, 'dxrpCW')]/a")
                onclick = link.attrib["onclick"]
                truncated_message_path = re.search(r"\('(.*)'\)", onclick).group(1)
                body = self._parse_truncated_message(truncated_message_path)

            request["messages"].append(
                {
                    "id": message.attrib["id"].split("_")[-1],
                    "sender": parsed_sender.group("name"),
                    "date": parsed_sender.group("date"),
                    "time": parsed_sender.group("time"),
                    "body": re.sub(r"\s+", " ", " ".join(body)).strip(),
                }
            )

        attachment_links = tree.xpath(
            "//div[@id='dvAttachments']/descendant::div[@class='qac_attachment']/input[contains(@id, 'hdnAWSUrl') or contains(@id, 'hdnAzureURL')]"
        )

        for link in attachment_links:
            if "value" in link.attrib:
                url = link.attrib["value"]
                uploaded_at_str = link.xpath("../../../td[1]/text()")[0].strip()
                metadata = parse_qs(urlparse(url).query)
                request["attachments"].append(
                    {
                        "url": link.attrib["value"],
                        "content-disposition": metadata["response-content-disposition"][
                            0
                        ],
                        "expires": datetime.fromtimestamp(int(metadata["Expires"][0])),
                        "uploaded_at": datetime.strptime(
                            uploaded_at_str, "%m/%d/%Y"
                        ).date(),
                    }
                )

        return request

    def _parse_truncated_message(self, truncated_message_endpoint):
        truncated_message_url = self.url_from_endpoint(truncated_message_endpoint)
        response = self.get(truncated_message_url)
        tree = lxml.html.fromstring(response.text)
        body = tree.xpath(".//div[@id='divMessage']//text()")
        return body

    def _check_logged_in(self, response):
        if "If you have used this service previously, please log in" in response.text:
            raise UnauthenticatedError


class CreateAccountForm:
    def __init__(self, session):
        self._session = session

        response = self._create_account_page()
        self.account_creation_page = response.request.url

        tree = lxml.html.fromstring(response.text)

        # find the table elements that are direct ancestors of labels
        # that have an <em> next to them indicating a required field,
        # and then find the non-hidden inputs descendants of those
        # tables
        required_inputs = tree.xpath(
            ".//table[tr/td/label[starts-with(@for, 'customer') and following-sibling::em]]//input[not(@type='hidden')]"
        )

        required_inputs += tree.xpath(
            ".//table[tr/td/span[starts-with(@id, 'customer') and following-sibling::em]]//input"
        )

        self.schema = self._generate_schema(required_inputs, response)
        self._post_keys = self._generate_post_keys(required_inputs)

        self._payload = self._secrets(tree, response)
        self._payload.update(self._form_values(tree))
        self._payload["__EVENTTARGET"] = "btnSaveData"
        self._payload["customerInfo$hiddenPasswordChanged"] = "1"

        self.captcha = self._captcha(tree)

        if self.captcha:
            self.schema["properties"]["captcha"] = {
                "type": "string",
                "pattern": "^[A-Z0-9]{4,6}$",
            }
            self.schema["required"].append("captcha")
            self._post_keys["captcha"] = "captchaFormLayout$CaptchaCodeTextBox"
            self._payload[
                "BDC_BackWorkaround_c_customerdetails_captchaformlayout_captcha"
            ] = 1

    def _generate_schema(self, required_inputs, response):
        properties = {}
        for element in required_inputs:
            try:
                label = element.attrib["aria-label"].lower().replace(" ", "_")
            except KeyError:
                label = element.attrib["name"]
            properties[label] = {"type": "string"}
            if element.attrib.get("role") == "combobox":
                pattern = rf"'uniqueID':'{re.escape(label)}\$DDD\$L'(?:[^}}]+}})+[^}}]+?'itemsInfo':(\[[^\]]*?\])"

                matches = re.search(pattern, response.text)
                options = ast.literal_eval(matches.group(1))
                properties[label]["enum"] = [option["value"] for option in options[1:]]

            elif element.getparent().getparent().attrib.get("role") == "checkbox":
                properties[label]["enum"] = ["U", "C"]

        # we'll handle duplicating the password elsewhere
        properties.pop("confirm_password")

        if "phone" in properties:
            properties["phone"] = {
                "type": "string",
                "pattern": "^[0-9]{10}$",
            }

        schema = {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

        jsonschema.Draft7Validator.check_schema(schema)

        return schema

    def _generate_post_keys(self, required_inputs):
        post_keys = {}
        for element in required_inputs:
            try:
                label = element.attrib["aria-label"].lower().replace(" ", "_")
            except KeyError:
                label = element.attrib["name"]
            post_keys[label] = [element.attrib["name"]]
            if element.attrib.get("role") == "combobox":
                post_keys[label].append(
                    element.xpath('../../..//input[@type="hidden"]')[0].name
                )

        return post_keys

    def _secrets(self, tree, response):
        payload = self._session._secrets(tree, response)

        captcha_hash_input = tree.xpath(
            '//input[@id="BDC_VCID_c_customerdetails_captchaformlayout_captcha"]'
        )

        if captcha_hash_input:
            payload[
                "BDC_VCID_c_customerdetails_captchaformlayout_captcha"
            ] = captcha_hash_input[0].value

        return payload

    def _form_values(self, tree):
        form_inputs = tree.xpath(
            ".//table[tr/td/label[starts-with(@for, 'customer')]]//input[not(@type='hidden')] | "
            ".//table[tr/td/label[starts-with(@for, 'customer')]]//textarea | "
            ".//table[tr/td/span[starts-with(@id, 'customer')]]//input"
        )

        form_values = {}

        for form_input in form_inputs:
            name = form_input.attrib["name"]
            form_values[name] = ""
            form_values[f"{name}$State"] = '{"validationState":""}'

        return form_values

    def _captcha(self, tree):
        captcha_info = {}

        try:
            (captcha_img,) = tree.xpath(
                '//img[@id="c_customerdetails_captchaformlayout_captcha_CaptchaImage"]'
            )
        except ValueError:
            captcha_jpeg = None
        else:
            captcha_jpeg = io.BytesIO(
                self._session.get(
                    self._session.domain + captcha_img.attrib["src"]
                ).content
            )

        if captcha_jpeg:
            captcha_info["jpeg"] = captcha_jpeg

        try:
            (captcha_wav_link,) = tree.xpath(
                '//a[@id="c_customerdetails_captchaformlayout_captcha_SoundLink"]'
            )
        except ValueError:
            captcha_wav = None
        else:
            captcha_wav = io.BytesIO(
                self._session.get(
                    self._session.domain + captcha_wav_link.attrib["href"]
                ).content
            )

        if captcha_wav:
            captcha_info["wav"] = captcha_wav

        return captcha_info

    def submit(self, required_inputs):
        jsonschema.validate(required_inputs, self.schema)

        payload = self._payload.copy()
        payload.update(
            {
                post_key: v
                for k, v in required_inputs.items()
                for post_key in self._post_keys[k]
            }
        )
        payload[self._post_keys["confirm_password"][0]] = required_inputs["password"]

        if "phone" in required_inputs:
            payload[
                "customerInfo$CustomerFormLayout$txtPhoneMask$State"
            ] = f'{{"rawValue":"{required_inputs["phone"]}","validationState":""}}'

        payload[
            "customerInfo$CustomerFormLayout$cf_2$State"
        ] = '{"rawValue":"","validationState":""}'

        try:
            response = self._session.post(self.account_creation_page, data=payload)
        except scrapelib.HTTPError as error:
            # Unfortunately, we don't get a clean success page, but if we
            # get redirected to the Home Page then we have been successful
            if "CustomerHome.aspx" in error.response.request.url:
                return True
            else:
                raise
        else:
            tree = lxml.html.fromstring(response.text)

            form_validation_errors = tree.xpath(
                '//div[@id="header_errors1"]//li/text()'
            )

            if not len(form_validation_errors):
                raise FormValidationError(
                    "The form did not validate for an unknown reason."
                )

            if "Email address already exists." in form_validation_errors:
                raise EmailAlreadyExists(
                    "The email address already exists in this instance."
                )

            # reset the captcha and secrets if we want to try again
            self.captcha = self._captcha(tree)
            self._payload.update(self._secrets(tree, response))

            if "The submitted code is incorrect." in form_validation_errors:
                raise IncorrectCaptcha("The submitted captcha was incorrect")

            for error in form_validation_errors:
                raise FormValidationError(
                    f'The form did not validate. The website reports this error: "{error}"'
                )

    def _create_account_page(self):
        response = self._session.get(
            self._session.url_from_endpoint("Login.aspx"), allow_redirects=True
        )

        tree = lxml.html.fromstring(response.text)

        (create_user_link,) = tree.xpath("//a[@id='lnkCreateUser']")

        response = self._session.get(
            self._session.url_from_endpoint(create_user_link.attrib["href"]),
            allow_redirects=True,
        )

        return response


class Form:
    def _form_values(self, tree, form_prefix):
        form_inputs = tree.xpath(
            f".//table[tr/td/label[starts-with(@for, '{form_prefix}')]]//input[not(@type='hidden')] | "
            f".//table[tr/td/label[starts-with(@for, '{form_prefix}')]]//textarea | "
            f".//table[tr/td/span[starts-with(@id, '{form_prefix}')]]//input"
        )

        form_values = {}

        for form_input in form_inputs:
            name = form_input.attrib["name"]
            is_radio_box = name.rsplit("$", 1)[-1].startswith("RB")
            if is_radio_box:
                form_values[name] = "U"
            else:
                form_values[name] = ""
                form_values[f"{name}$State"] = '{"validationState":""}'

        return form_values

    def _inputs(self, required_inputs_tables, source_text):
        required_inputs = {}

        for table in required_inputs_tables:
            if table.xpath(".//input[@role='combobox']"):
                klass = ComboBox
            elif table.xpath(".//textarea"):
                klass = TextArea
            elif table.xpath(".//table[@role='radiogroup']"):
                klass = RadioGroup
            elif table.xpath(".//span[@role='checkbox']"):
                klass = CheckBox
            else:
                klass = Input

            input_element = klass(table, source_text)
            required_inputs[input_element.label] = input_element

        return required_inputs

    def _generate_schema(self, required_inputs):
        properties = {
            key: element.properties for key, element in required_inputs.items()
        }
        schema = {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

        jsonschema.Draft7Validator.check_schema(schema)

        return schema


class RequestForm(Form):
    def __init__(self, session, request_type):
        self._session = session

        # come back and fix this request types
        url = (
            self._session.url_from_endpoint("RequestOpen.aspx")
            + f"?rqst={request_type}"
        )
        response = self._session.get(url)
        self._session._check_logged_in(response)

        self.request_url = response.url

        tree = lxml.html.fromstring(response.text)

        # find the table elements that are direct ancestors of labels
        # that have an <em> next to them indicating a required field
        required_inputs_tables = tree.xpath(
            ".//table[tr/td/label[starts-with(@for, 'request') and following-sibling::em]] | "
            ".//table[tr/td/span[starts-with(@id, 'request') and following-sibling::em]]"
        )

        self.required_inputs = self._inputs(required_inputs_tables, response.text)

        self.schema = self._generate_schema(self.required_inputs)

        self._payload = self._form_values(tree, "request")
        self._payload.update(self._session._secrets(tree, response))
        self._payload["__EVENTTARGET"] = "btnSaveData"

        captcha = Captcha(
            self._session,
            tree,
            "c_requestopen_captchaformlayout_reqstopencaptcha_CaptchaImage",
            "c_requestopen_captchaformlayout_reqstopencaptcha_SoundLink",
            "captchaFormLayout$reqstOpenCaptchaTextBox",
            "BDC_VCID_c_requestopen_captchaformlayout_reqstopencaptcha",
            "BDC_BackWorkaround_c_requestopen_captchaformlayout_reqstopencaptcha",
        )
        self.captcha = captcha.info

        if self.captcha:
            self.schema["properties"]["captcha"] = {
                "type": "string",
                "pattern": "^[A-Z0-9]{4,6}$",
            }
            self.schema["required"].append("captcha")
            self.required_inputs["captcha"] = captcha

    def submit(self, required_inputs):
        jsonschema.validate(required_inputs, self.schema)

        payload = self._payload.copy()
        payload.update(
            {
                post_key: value
                for form_key, input_string in required_inputs.items()
                for post_key, value in self.required_inputs[form_key].fill(input_string)
            }
        )

        try:
            response = self._session.post(self.request_url, data=payload)
        except scrapelib.HTTPError as error:
            # Unfortunately, we don't get a clean success page, but if we
            # get redirected to the Home Page then we have been successful
            if "CustomerHome.aspx" in error.response.request.url:
                return True
            else:
                raise
        else:
            tree = lxml.html.fromstring(response.text)

            form_validation_errors = tree.xpath(
                '//div[@id="header_errors1"]//li/text()'
            )

            if not len(form_validation_errors):
                raise FormValidationError(
                    "The form did not validate for an unknown reason."
                )

            if "Email address already exists." in form_validation_errors:
                raise EmailAlreadyExists(
                    "The email address already exists in this instance."
                )

            # reset the captcha and secrets if we want to try again
            self.captcha = self._captcha(tree)
            self._payload.update(self._secrets(tree, response))

            if "The submitted code is incorrect." in form_validation_errors:
                raise IncorrectCaptcha("The submitted captcha was incorrect")

            for error in form_validation_errors:
                raise FormValidationError(
                    f'The form did not validate. The website reports this error: "{error}"'
                )
