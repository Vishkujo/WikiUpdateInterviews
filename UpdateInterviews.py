import os
import requests
import json
from dotenv import load_dotenv
import mwparserfromhell
from datetime import datetime
from dateutil.parser import parse

load_dotenv()

API_URL = os.getenv('MEDIAWIKI_API_URL')
USERNAME = os.getenv('MEDIAWIKI_USERNAME')
PASSWORD = os.getenv('MEDIAWIKI_PASSWORD')
MEDIAWIKI_LANGUAGE_CODES = ['fr', 'es', 'ru', 'it', 'de', 'nl', 'pt-br', 'fa', 'ro', 'pl', 'he', 'ur', 'th', 'sv', 'ja']

def parse_custom_date(date_string):
    date_parts = date_string.split()
    if len(date_parts) == 3:  # M D, Y format
        return parse(date_string, fuzzy=True)
    elif len(date_parts) == 2:  # M Y format
        return parse("1 " + date_string, fuzzy=True)
    elif len(date_parts) == 1:  # Y format
        return parse("1 January " + date_string, fuzzy=True)
    else:
        return datetime.min

def login():
    session = requests.Session()

    # Fetch login token
    response = session.get(API_URL, params={
        'action': 'query',
        'meta': 'tokens',
        'type': 'login',
        'format': 'json'
    })
    login_token = response.json()['query']['tokens']['logintoken']

    # Log in
    response = session.post(API_URL, data={
        'action': 'login',
        'lgname': USERNAME,
        'lgpassword': PASSWORD,
        'lgtoken': login_token,
        'format': 'json'
    })

    login_data = response.json()
    if login_data['login']['result'] == 'Success':
        print('Logged in successfully')
        return session
    else:
        print('Error logging in:', login_data)
        return None

def extract_infobox_parameters(wikitext):
    parsed_wikitext = mwparserfromhell.parse(wikitext)
    infoboxes = parsed_wikitext.filter_templates(matches='Infobox')
    
    if not infoboxes:
        return None
    
    infobox = infoboxes[0]
    parameters = ['part', 'title', 'cover', 'date', 'interviewee', 'translation', 'transcript', 'type', 'media', 'display', 'publication']
    extracted_parameters = {}
    
    for parameter in parameters:
        try:
            value = infobox.get(parameter).value.strip()
            if parameter == 'interviewee':
                value = value.split(', ')
            extracted_parameters[parameter] = value if isinstance(value, list) else str(value)
        except ValueError:
            extracted_parameters[parameter] = None
    
    return extracted_parameters

def fetch_categories(session, title):
    response = session.get(API_URL, params={
        'action': 'query',
        'prop': 'categories',
        'titles': title,
        'cllimit': 'max',
        'format': 'json'
    })
    data = response.json()
    page_id = list(data['query']['pages'].keys())[0]
    categories = data['query']['pages'][page_id].get('categories', [])
	
    excluded_categories = ['Category:Interviews', 'Category:Pages Needing Expansion']
    custom_order = ['Manga', 'Anime', 'OVA', 'Film', 'TV Drama', 'Video Game', 'Novel', 'Music', 'Part 1', 'Part 2', 'Part 3', 'Part 4', 'Part 5', 'Part 6', 'Part 7', 'Part 8', 'Part 9', 'Thus Spoke Kishibe Rohan', 'Cool Shock B.T.', 'Baoh the Visitor', 'Miscellaneous']
    order = {key: i for i, key in enumerate(custom_order)}
    categories = [category['title'].replace('Category:', '').replace(' Interviews', '') for category in categories if category['title'] not in excluded_categories]
    categories.sort(key=lambda x: order.get(x, len(custom_order)))
    return categories

def fetch_page_content(session, title):
    response = session.get(API_URL, params={
        'action': 'query',
        'prop': 'revisions',
        'rvprop': 'content',
        'titles': title,
        'format': 'json'
    })
    data = response.json()
    page_id = list(data['query']['pages'].keys())[0]
    content = data['query']['pages'][page_id]['revisions'][0]['*']
    
    return content

def update_json_page(session):
    response = session.get(API_URL, params={
        'action': 'query',
        'list': 'allpages',
        'apnamespace': 7000,
        'aplimit': 'max',
        'format': 'json'
    })
    data = response.json()

    interviews = []
    for page in data['query']['allpages']:
        title = page['title']
        if not any(title.endswith('/' + lang_code) for lang_code in MEDIAWIKI_LANGUAGE_CODES):
            content = fetch_page_content(session, title)
            infobox_data = extract_infobox_parameters(content)

            # Fetch categories and use them as tags
            categories = fetch_categories(session, title)
            if infobox_data is not None:
                infobox_data['title'] = title.replace('Interview:', '')  # Set the title directly from the API, without the "Interview:" namespace
                infobox_data['tags'] = categories
                interviews.append(infobox_data)

    interviews.sort(key=lambda x: parse_custom_date(x['date'] if x['date'] else ''))
    
    page_data = {'interviews': interviews}

    csrf_token = session.get(API_URL, params={
        'action': 'query',
        'meta': 'tokens',
        'type': 'csrf',
        'format': 'json'
    }).json()['query']['tokens']['csrftoken']

    edit_response = session.post(API_URL, data={
        'action': 'edit',
        'title': 'JoJo_Wiki:Interviews',  # Change this to the desired page title
        'contentmodel': 'json',
        'text': json.dumps(page_data),
        'token': csrf_token,
        'format': 'json'
    })

    edit_data = edit_response.json()
    if edit_data['edit']['result'] == 'Success':
        print('Page updated successfully')
    else:
        print('Error updating page:', edit_data)

def main():
    session = login()
    update_json_page(session)

if __name__ == '__main__':
    main()
