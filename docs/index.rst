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

   # Instantiate an instance of the GovQA client
   client = GovQA(
        os.environ["GOVQA_DOMAIN"],
        os.environ["GOVQA_USERNAME"],
        os.environ["GOVQA_PASSWORD"],
    )

    # List requests for the authenticated user
    response = client.list_requests()

    # Get details of a specific request
    client.get_request(request_id)

API
===

:class:`GovQA` Object
--------------------------

.. autoclass:: govqa.base.GovQA

   .. automethod:: list_requests

   .. automethod:: get_request

