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
        captcha = input("Capcha please: ")
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
    if captcha:
        with open("out.jpg", "wb") as f:
            f.write(form.captcha["jpeg"].getbuffer())


client.login(EMAIL_ADDRESS, PASSWORD)

# List requests for the authenticated user
requests = client.list_requests()

for request in requests:
    # Get details of a specific request
    details = client.get_request(request["id"])
    print(details)
    break
