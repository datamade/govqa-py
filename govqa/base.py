import re
from datetime import datetime
import dateutil.parser
from urllib.parse import parse_qs, urlparse

import jsonschema
import lxml.html
import scrapelib

from .input_types import (
    Captcha,
    CheckBox,
    ComboBox,
    Input,
    Password,
    Phone,
    RadioGroup,
    TextArea,
)


class UnauthenticatedError(RuntimeError):
    pass


class FormValidationError(RuntimeError):
    pass


class IncorrectCaptcha(FormValidationError):
    pass


class EmailAlreadyExists(FormValidationError):
    pass


class UnsupportedSite(RuntimeError):
    pass


class GovQA(scrapelib.Scraper):
    """
    Client for programmatically interacting with GovQA instances.

    :param domain: Root domain of the GovQA instance to interact with, e.g.,
        https://governorny.govqa.us
    :type domain: str
    """

    def __init__(self, domain, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.domain = domain.rstrip("/")

        response = self.get(self.url_from_endpoint(""), allow_redirects=True)

        if "supporthome.aspx" not in response.url.lower():
            raise UnsupportedSite(f"{domain} does not seem to be a valid GovQA site")

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
        """
        Get form for creating a new account

        :returns: an helper for creating a new account
        :rtype: CreateAccountForm
        """
        return CreateAccountForm(self)

    def request_form(self, request_type=1):
        """
        Get form for creating a new public record request

        :param request_type: Some site have more than one request type (i.e.
                             commercial vs non-commercial). Indicates which one
                             you want to use.
        :type request_type: int
        :returns: an wrapper for creating a new record request
        :rtype: RequestForm

        """
        return RequestForm(self, request_type)

    def login(self, username, password):
        """
        Login into the site

        :param username: user name for thie site
        :type username: str
        :param password: password for thie site
        :type password: str
        """
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

        response = self.post(response.url, data=payload, allow_redirects=True)

        try:
            self._check_logged_in(response)
        except UnauthenticatedError:
            raise UnauthenticatedError(
                "Couldn't log in, check your username and password"
            )

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
                           list_requests(). N.b., the reference number is not
                           the identifier.
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
                if "response-content-disposition" in metadata:
                    content_disposition = metadata["response-content-disposition"][0]
                    expires = datetime.fromtimestamp(int(metadata["Expires"][0]))
                elif "rscd" in metadata:
                    content_disposition = metadata["rscd"][0]
                    expires = dateutil.parser.parse(metadata["se"][0])
                request["attachments"].append(
                    {
                        "url": link.attrib["value"],
                        "content-disposition": content_disposition,
                        "expires": expires,
                        "uploaded_at": dateutil.parser.parse(uploaded_at_str).date(),
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
        results = re.search('dtrum.identifyUser\("(.*)"\);', response.text).group(1)
        if not results.split(";")[-1]:
            raise UnauthenticatedError(
                "This method requires authentication, please run the `login` method before calling this method"
            )


class Form:
    def _process_inputs(self, required_inputs_tables, tree, response):
        self.required_inputs = self._inputs(required_inputs_tables, response.text)

        self.schema = self._generate_schema(self.required_inputs)

        self._payload = self._form_values(tree, "request")
        self._payload.update(self._session._secrets(tree, response))
        self._payload["__EVENTTARGET"] = "btnSaveData"

        captcha = Captcha(self._session, tree, **self._captcha_config)
        self.captcha = captcha.info
        """ docs """

        if self.captcha:
            self.schema["properties"]["captcha"] = {
                "type": "string",
                "pattern": "^[A-Z0-9]{4,6}$",
            }
            self.schema["required"].append("captcha")
            self.required_inputs["captcha"] = captcha

    def _reset_payload(self, tree, response):
        captcha = Captcha(self._session, tree, **self._captcha_config)
        self.captcha = captcha.info
        if "captcha" in self.required_inputs:
            self.required_inputs["captcha"] = captcha
        self._payload.update(self._session._secrets(tree, response))

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

        is_password = False
        password = None
        confirm_password_table = None

        for table in required_inputs_tables:
            if table.xpath(".//input[@role='combobox']"):
                klass = ComboBox
            elif table.xpath(".//textarea"):
                klass = TextArea
            elif table.xpath(".//table[@role='radiogroup']"):
                klass = RadioGroup
            elif table.xpath(".//span[@role='checkbox']"):
                klass = CheckBox
            elif table.xpath(
                ".//input[@name='customerInfo$CustomerFormLayout$txtPhoneMask']"
            ):
                klass = Phone
            elif table.xpath(
                ".//input[@name='customerInfo$CustomerFormLayout$txtPassword']"
            ):
                is_password = True
                klass = Password
            elif table.xpath(
                ".//input[@name='customerInfo$CustomerFormLayout$txtConfirmPassword']"
            ):
                # we'll handle the confirm-password inputs in the password input
                confirm_password_table = table
                continue
            else:
                klass = Input

            input_element = klass(table, source_text)
            required_inputs[input_element.label] = input_element
            if is_password:
                password = input_element
                is_password = False

        if confirm_password_table is not None:
            password.add_confirmation(confirm_password_table)

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


class CreateAccountForm(Form):
    """
    Wrapper for interacting with a site's account creation form

    Attributes:
       captcha (dict or None): Dictionary of captcha jpeg and wav files as
                               BytesIO objects, if the the form has a captcha.
                               Otherwise, captcha has a value of None.
       schema (dict): A `JSON Schema <https://json-schema.org/>`_ representing
                      the required fields to create an account and their
                      format.
    """

    _captcha_config = {
        "img_id": "c_customerdetails_captchaformlayout_captcha_CaptchaImage",
        "wav_link_id": "c_customerdetails_captchaformlayout_captcha_SoundLink",
        "input_name": "captchaFormLayout$CaptchaCodeTextBox",
        "captcha_hash_input_name": "BDC_VCID_c_customerdetails_captchaformlayout_captcha",
        "workaround_input_name": "BDC_BackWorkaround_c_customerdetails_captchaformlayout_captcha",
    }

    def __init__(self, session):
        self._session = session

        response = self._create_account_page()
        self.account_creation_page = response.request.url

        tree = lxml.html.fromstring(response.text)

        # find the table elements that are direct ancestors of labels
        # that have an <em> next to them indicating a required field
        required_inputs_tables = tree.xpath(
            ".//table[tr/td/label[starts-with(@for, 'customer') and following-sibling::em]] | "
            ".//table[tr/td/span[starts-with(@id, 'customer') and following-sibling::em]]"
        )

        self._process_inputs(required_inputs_tables, tree, response)

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

    def submit(self, required_inputs):
        """
        Submit fields to create a new account. If the submission is
        unsuccessful, the captcha will be refreshed.

        :param required_inputs: dictionary containing the field values for
                                creating a new account. If the dictionary is
                                not compatible with the :ref:`schema` then an
                                informative error will be raised.
        :type required_inputs: dict
        :returns: Returns True if account created successfully
        :rtype: bool
        """

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

            self._reset_payload(tree, response)

            if "The submitted code is incorrect." in form_validation_errors:
                raise IncorrectCaptcha("The submitted captcha was incorrect")

            for error in form_validation_errors:
                raise FormValidationError(
                    f'The form did not validate. The website reports this error: "{error}"'
                )


class RequestForm(Form):
    """
    Wrapper for interacting with the site's form to submit a new record
    request.

    Attributes:
       captcha (dict or None): Dictionary of captcha jpeg and wav files as
                               BytesIO objects, if the the form has a captcha.
                               Otherwise, captcha has a value of None.
       schema (dict): A `JSON Schema <https://json-schema.org/>`_ representing
                      the required fields to create a new record request.
    """

    _captcha_config = {
        "img_id": "c_requestopen_captchaformlayout_reqstopencaptcha_CaptchaImage",
        "wav_link_id": "c_requestopen_captchaformlayout_reqstopencaptcha_SoundLink",
        "input_name": "captchaFormLayout$reqstOpenCaptchaTextBox",
        "captcha_hash_input_name": "BDC_VCID_c_requestopen_captchaformlayout_reqstopencaptcha",
        "workaround_input_name": "BDC_BackWorkaround_c_requestopen_captchaformlayout_reqstopencaptcha",
    }

    def __init__(self, session, request_type):
        self._session = session

        response = self._session.get(
            self._session.url_from_endpoint("RequestOpen.aspx"),
            params={"rqst": request_type},
        )

        self._session._check_logged_in(response)

        self.request_url = response.url

        tree = lxml.html.fromstring(response.text)

        # find the table elements that are direct ancestors of labels
        # that have an <em> next to them indicating a required field
        required_inputs_tables = tree.xpath(
            ".//table[tr/td/label[starts-with(@for, 'request') and following-sibling::em]] | "
            ".//table[tr/td/span[starts-with(@id, 'request') and following-sibling::em]]"
        )

        self._process_inputs(required_inputs_tables, tree, response)

    def submit(self, required_inputs):
        """
        Submit fields to create a new record request. If the submission is
        unsuccessful, the captcha will be refreshed.

        :param required_inputs: dictionary containing the field values for
                                creating a new record request. If the
                                dictionary is not compatible with the
                                :ref:`schema` then an informative error will be
                                raised.
        :type required_inputs: dict
        :returns: Returns the reference number if record request created
                  successfully
        :rtype: str
        """

        jsonschema.validate(required_inputs, self.schema)

        payload = self._payload.copy()
        payload.update(
            {
                post_key: value
                for form_key, input_string in required_inputs.items()
                for post_key, value in self.required_inputs[form_key].fill(input_string)
            }
        )

        response = self._session.post(self.request_url, data=payload)

        tree = lxml.html.fromstring(response.text)

        try:
            reference_number = tree.xpath(
                './/span[@id="ConfirmFormLayout_roReferenceNo"]'
            )[0].text
            return reference_number
        except IndexError:
            form_validation_errors = tree.xpath(
                '//div[@id="header_errors1"]//li/text()'
            )

            if not len(form_validation_errors):
                raise FormValidationError(
                    "The form did not validate for an unknown reason."
                )

            self._reset_payload(tree, payload)

            if "The submitted CAPTCHA code is incorrect" in form_validation_errors:
                raise IncorrectCaptcha("The submitted captcha was incorrect")

            for error in form_validation_errors:
                raise FormValidationError(
                    f'The form did not validate. The website reports this error: "{error}"'
                )
