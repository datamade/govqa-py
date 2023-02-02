from scrapelib import Scraper


class GovQA(Scraper):

	# S(hash) is an auto-generated session id – you can start with whatever in S(foo) and it will redirect to a
	# valid session id
	SCREENS = {
		"HOME": "https://chicagoil.govqa.us/WEBAPP/_rs/(S(avkc0dc23pt3ekhsam5lecoa))/SupportHome.aspx",
		"LOG_IN": "https://chicagoil.govqa.us/WEBAPP/_rs/(S(avkc0dc23pt3ekhsam5lecoa))/Login.aspx",
		"CREATE_ACCOUNT": "https://chicagoil.govqa.us/WEBAPP/_rs/(S(avkc0dc23pt3ekhsam5lecoa))/CustomerDetails.aspx"
	}

"""
GET https://chicagoil.govqa.us/WEBAPP/_rs/(S(lcwowhduu5obtbicm53kcofp))/SupportHome.aspx

GET https://chicagoil.govqa.us/WEBAPP/_rs/(S(avkc0dc23pt3ekhsam5lecoa))/Login.aspx

	GET a[@id="lnkCreateUser"] -> href

GET https://chicagoil.govqa.us/WEBAPP/_rs/(S(avkc0dc23pt3ekhsam5lecoa))/CustomerDetails.aspx

	sSessionID=
	new=1
	target=YpURA3m6cNU+N1K9kEqQhsrfcDJG9Ka8RWiy1M8DmiH7DCBh2zM3lwy8FVOXbT85OAivQa7Mg/79jh5erufutULr4aDy8MywN9uXgWeZm5XbH2bkP6op/sOHh5EWlh7hWdimVw/ssZAf9BnrYGhyDudfLIUWESe3lZNVf0X4zxJTB6DWi9T768DacazgxnE1

"""

	def create_account():
		...

	def log_in():
		self.get()
		...

	def reset_password():
		...

	def submit_request():
		...

	def submit_request_attachments():
		...

	def retrieve_message():
		...

	def send_message():

	def retrieve_request_response():
		...

