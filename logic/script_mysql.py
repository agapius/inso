import time
import datetime
import requests
from bs4 import BeautifulSoup
import re
import mysql.connector
import smtplib

# this script is constantly running. it mainy builds on the inso.py

#database_location = '/Users/Niklas/Desktop/Code/inso/inso/site.db'
URL = 'https://www.insolvenzbekanntmachungen.de/cgi-bin/bl_suche.pl'
gmail_user = 'insolvenz.app@gmail.com'
gmail_pw = 'insolvenz'

### EMAIL CLIENT

'''try: 
	server = smtplib.SMTP('smtp.gmail.com', 587)
	server.login(gmail_user, gmail_pw)
except:
	print('something went wrong')'''

### REGEX PATTERNS

link_pattern = "\('(.*?)'\)"
datum_pattern = "(\d\d\d\d)-(\d\d)-(\d\d)"
gesellschaften_pattern = "(gmbh)|(ag)|(mbh)|(projektgesellschaft)|(ug)|(gesellschaft)"
regNo_pattern = "\d*((\w|.).(IN|IK).(\d+\/\d+))"
street_pattern = "(straße)|(strasse)"
pages_pattern = "(wurden).(\d+).(Treffer)"
#Fails:
regNo_fails = []
datum_fails = []
link_fails = []

### FUNCTIONS

# timefunc returns the date of yesterday
def timefunc():
	timedelta = datetime.timedelta(days=-1)
	yesterday = datetime.date.today() + timedelta
	#yesterday = datetime.date.today()
	time = str(yesterday)
	print(time)
	year = time[0:4]
	month = time[5:7]
	day = time[8:]

	return day, month, year

def get_date(item):
	if re.match(datum_pattern, item.get_text(strip=True)):
		datum_raw_match = re.match(datum_pattern, item.get_text(strip=True))
		datum = datum_raw_match.group(0)
		return datum
	else:
		datum_fails.append(item)


def get_ort(item):
	beschreibung_raw_match = re.split(datum_pattern, item.get_text(strip=True))	
	beschreibung = beschreibung_raw_match[4]
	text = re.split(",",beschreibung)
	if re.search(gesellschaften_pattern, text[0].lower()):
		if re.search(street_pattern, text[1].strip(), re.IGNORECASE):
			ort = text[1].strip() +text[2]
		else:
			ort = text[1].strip() 
	else:
		if re.search(street_pattern, text[1].strip(), re.IGNORECASE):
			ort = text[2].strip() + text[3]
		else:	
			ort = text[2].strip()
	return ort


def get_inhaber(item):
	beschreibung_raw_match = re.split(datum_pattern, item.get_text(strip=True))	
	beschreibung = beschreibung_raw_match[4]
	text = re.split(",",beschreibung)
	if re.search(gesellschaften_pattern,text[0].lower()):
		inhaber = text[0]
	else:
		inhaber = text[0]+text[1]
	return inhaber


def get_regNo(item):

	if re.search(regNo_pattern, item.get_text(strip=True)):
		regNo_raw_match = re.search(regNo_pattern, item.get_text(strip=True))	
		regNo = regNo_raw_match.group(0)
		return regNo
	else:
		regNo_fails.append(item.get_text(strip=True))
		return None


def get_link(item):
	if re.findall(link_pattern, item['href']):
		link_raw_match = re.findall(link_pattern, item['href'])
		link = "https://www.insolvenzbekanntmachungen.de" + link_raw_match[0]
		return link
	else:
		link_fails.append(item)
		return None


def get_metadata(item):
	datum = get_date(item)
	inhaber = get_inhaber(item)
	ort = get_ort(item)
	regNo = get_regNo(item)
	link = get_link(item)
	return datum, inhaber, ort, regNo, link


def get_bekanntmachung(link):
	res = s.get(link)
	soup = BeautifulSoup(res.text, "html.parser")
	return soup.body.prettify()

def get_data_from_page(URL, payload):
	print('get_data_from_page')
	with requests.Session() as s:
		s.headers = {"User-Agent":"Mozilla/5.0"}
		s.headers.update({'Content-Type': 'application/x-www-form-urlencoded'})
		res = s.post(URL, data = payload)
		soup = BeautifulSoup(res.text, "html.parser")
		#print(soup)
		suchergebnisse = soup.select("b li a")
		#print(suchergebnisse[0])
		data_from_page = []
		for item in suchergebnisse:
			datum, inhaber, ort, regNo, link = get_metadata(item)
			rowID = None
			data_from_page.append((rowID, regNo, datum, inhaber, ort, link))
			#bekanntmachung = get_bekanntmachung(link)
	return data_from_page

def get_pages(URL, payload):
	print('get_pages')
	with requests.Session() as s:
		s.headers = {"User-Agent":"Mozilla/5.0"}
		s.headers.update({'Content-Type': 'application/x-www-form-urlencoded'})
		res = s.post(URL, data = payload)
		soup = BeautifulSoup(res.text, "html.parser")
		pages_raw_match = re.search(pages_pattern, soup.get_text())	
		if pages_raw_match is None:
			return False
		pagesNo = int(pages_raw_match.group(2))
		pagesNo = round(pagesNo / 100)
		pagesNo += 1
		return pagesNo


def insert_into_database(database_location, data_from_page):
	print('insert_into_database')
	mydb = mysql.connector.connect(host='localhost', user='username', database='mydatab')
	cur= mydb.cursor()
	for verfahren in data_from_page:
		cur.execute("INSERT INTO inso VALUES (?,?,?,?,?,?)", verfahren)
		mydb.commit()
	mydb.close()

def update_database(day, month, year):
	print('update_database')
	payload = 'Suchfunktion=uneingeschr&Absenden=Suche+starten&Bundesland=--+Alle+Bundesl%E4nder+--&Gericht=--+Alle+Insolvenzgerichte+--&Datum1={}.{}.{}&Datum2={}.{}.{}&Name=&Sitz=&Abteilungsnr=&Registerzeichen=--&Lfdnr=&Jahreszahl=--&Registerart=--+keine+Angabe+--&select_registergericht=&Registergericht=--+keine+Angabe+--&Registernummer=&Gegenstand=--+Alle+Bekanntmachungen+innerhalb+des+Verfahrens+--&matchesperpage=100&page=1&sortedby=Datum'.format(day, month, year[2:], day, month, year[2:])
	#database_location = '/Users/Niklas/Desktop/Code/inso/inso/site.db'


	pagesNo = get_pages(URL, payload)
	if pagesNo == False:
		return False
	print(pagesNo)
	page = 1 

	all_data = []

	while page<=pagesNo:

		payload = 'Suchfunktion=uneingeschr&Absenden=Suche+starten&Bundesland=--+Alle+Bundesl%E4nder+--&Gericht=--+Alle+Insolvenzgerichte+--&Datum1={}.{}.{}&Datum2={}.{}.{}&Name=&Sitz=&Abteilungsnr=&Registerzeichen=--&Lfdnr=&Jahreszahl=--&Registerart=--+keine+Angabe+--&select_registergericht=&Registergericht=--+keine+Angabe+--&Registernummer=&Gegenstand=--+Alle+Bekanntmachungen+innerhalb+des+Verfahrens+--&matchesperpage=100&page='.format(day, month, year[2:], day, month, year[2:]) + str(page) + '&sortedby=Datum'
		#print(payload)
		data_from_page = get_data_from_page(URL, payload)
		#save_data gets data_from_page in form of an array of tuples
		insert_into_database(database_location, data_from_page)
		#then a function (safe_data) is called, which saves the data in a mysql database
		print(page)
		
		page = page + 1
		all_data = all_data + data_from_page

		"""#print failures to txt
		with open('log.txt', 'a') as f:
			f.write('regNo failures:\n')
			for failure in regNo_fails:
				f.write(failure)

			f.write('\n')
			f.write('datum failures:\n')
			for failure in datum_fails:
				f.write(failure)

			f.write('\n')
			f.write('link failures:\n')
			for failure in link_fails:
				f.write(failure)
		f.close()"""

	return all_data

def get_user_verfahren():
	print('get_user_verfahren')
	#database_location = '/Users/Niklas/Desktop/Code/inso/inso/site.db'
	mydb = mysql.connector.connect(host='localhost', user='username', database='mydatab')
	cursor = mydb.cursor()
	cursor.execute("SELECT * FROM post")
	user = cursor.fetchall()
	return user

def send_mail(user, verfahren):
	gmail_user = 'insolvenz.app@gmail.com'
	gmail_pw = 'insolvenz'
	sent_from = 'insolvenz.app@gmail.com'
	to = user[1]
	subject = 'Neue bekanntmachung: {}'.format(user[0])
	body = 'Hallo {}! Bei dem von Dir abbonierten Verfahren {} gibt es eine neue Bekanntmachung. Hier ist der Link dazu: {}'.format(user[2], user[0], verfahren[5])

	email_text = 'From: {} \n To: {} \n Subject: {} \n {}'.format(sent_from, to, subject, body)

	try: 
		sever = smtplib.SMTP_SLL('smtp.gmail.com', 587)
		sever.ehlo()
		sever.login(gmail_user, gmail_pw)
		sever.sendmail(sent_from, to, email_text)
		sever.close()
		print('Email send')
	except:
		print('something went from')



### BODY

while True:
	print('starting up')
	log = open('log.txt', 'a')
	log.write('Preparing for new day:' + str(datetime.date.today()) + '\n')
	log.close()

	day, month, year = timefunc()
	print('Day' + day)
	print('Month' + month)
	print('Year' + year)

	updates = update_database(day, month, year)		# this scrapes all bekanntmachungen after latest bekanntmachung, inserts them in database, and returns the data for analysis
	if updates is False:
		print('nothing found today') 
		time.sleep(43200)
		continue

	update_counter = 0

	user_verfahren = get_user_verfahren()		# looks up in the database, and returns a dictionary with key= user and value = verfahren
	print(user_verfahren)

	log = open('log.txt', 'a')
	for user in user_verfahren:
		for verfahren in updates: 
			if user[1] == verfahren[1]:
				send_mail(user, verfahren)
				update_counter += 1
				#log_data = 'Mail send to' + user + ',' + 'verfahren' + '' + str(datetime.datetime.now())
				#log.write(log_data)

	#log_entry = 'Finished updating. ' + str(update_counter) + 'Mails send.' + str(len(updates)) + 'scraped.' + str(datetime.datetime.today()) +'\n')

	time.sleep(43200) 					        # script sleeps for 24 hourss