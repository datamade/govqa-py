.. GovQA-Py documentation master file, created by
   sphinx-quickstart on Fri Apr  7 08:31:32 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

GovQA-Py Documentation
======================

A Python client for interacting with GovQA, a public records request management
platform owned by Granicus.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Setup
-----

Get the library and its dependencies using `pip <https://pypi.python.org/pypi/pip>`_:

::

    pip install govqa

Usage
-----

::

    from govqa import GovQA, IncorrectCaptcha
    
    DOMAIN = ""
    EMAIL_ADDRESS = ""
    PASSWORD = ""
    
    # Instantiate an instance of the GovQA client
    client = GovQA(DOMAIN, retry_attempts=3)
    
    # get a new account form
    form = client.new_account_form()
    
    # If there are captcha's write to disk. alternatively you could try to solve them
    if form.captcha:
        with open("out.jpg", "wb") as f:
            f.write(form.captcha["jpeg"].getbuffer())
    
    success = False
    captcha = None
    while not success:
        if form.captcha:
            captcha = input("Captcha please: ")
        try:
            success = form.submit(
                {
                    "email_address": EMAIL_ADDRESS,
                    "password": PASSWORD,
                    "phone": "5299299999",
                    "captcha": captcha,
                }
            )
        except IncorrectCaptcha:
            pass
        if form.captcha:
            with open("out.jpg", "wb") as f:
                f.write(form.captcha["jpeg"].getbuffer())
    
    
    client.login(EMAIL_ADDRESS, PASSWORD)
    
    form = client.request_form(request_type=3)
    if form.captcha:
        with open("out.jpg", "wb") as f:
            f.write(form.captcha["jpeg"].getbuffer())
    captcha = input("Captcha please: ")
    
    reference_number = form.submit(
        {
            "type_of_record_requested": "Employee Information",
            "describe_the_record_requested": "YOUR_REQUEST_TEXT",
            "member_of_the_media": "No",
            "preferred_method_to_receive_record": "Electronic via FOIA Center",
            "format": "PDF",
            "captcha": captcha,
        }
    )
    
    
    # List requests for the authenticated user
    requests = client.list_requests()
    
    for request in requests:
        # Get details of a specific request
        details = client.get_request(request["id"])
        print(details)
    
API
===

.. autoclass:: govqa.GovQA

   .. automethod:: new_account_form

   .. automethod:: login		   

   .. automethod:: request_form		   

   .. automethod:: list_requests

   .. automethod:: get_request
		   
.. autoclass:: govqa.base.CreateAccountForm

   .. automethod:: submit

.. autoclass:: govqa.base.RequestForm	       

   .. automethod:: submit
