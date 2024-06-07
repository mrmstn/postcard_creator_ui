import base64
import datetime
import hashlib
import logging
import re
import secrets
import urllib
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests_toolbelt.utils import dump
from urllib3 import Retry

from postcard_creator.postcard_creator import PostcardCreatorException, PostcardCreatorTokenInvalidException

LOGGING_TRACE_LVL = 5
logger = logging.getLogger('postcard_creator')
logging.addLevelName(LOGGING_TRACE_LVL, 'TRACE')
setattr(logger, 'trace', lambda *args: logger.log(LOGGING_TRACE_LVL, *args))


def base64_encode(string):
    encoded = base64.urlsafe_b64encode(string).decode('ascii')
    return encoded.rstrip("=")


def base64_decode(string):
    padding = 4 - (len(string) % 4)
    string = string + ("=" * padding)
    return base64.urlsafe_b64decode(string)


def _log_response(h):
    for h in h.history:
        logger.debug(h.request.method + ': ' + str(h) + ' ' + h.url)
    logger.debug(h.request.method + ': ' + str(h) + ' ' + h.url)


def _print_request(response):
    logger.debug(' {} {} [{}]'.format(response.request.method, response.request.url, response.status_code))


def _dump_request(response):
    _print_request(response)
    data = dump.dump_all(response)
    try:
        logger.debug(data.decode())
    except Exception:
        data = str(data).replace('\\r\\n', '\r\n')
        logger.debug(data)


def _log_and_dump(r):
    _log_response(r)
    _dump_request(r)


class NoopToken:
    def __init__(self, token):
        self.token = token
        self.token_implementation = 'swissid'


class Token(object):
    AUTHENTICATE_MTAN = "AUTHENTICATE_MTAN"
    ACTION_SEND_DEVICE_PRINT = "SEND_DEVICE_PRINT"
    client_id = 'ae9b9894f8728ca78800942cda638155'
    client_secret = '89ff451ede545c3f408d792e8caaddf0'

    def __init__(self, _protocol='https://'):
        self.protocol = _protocol
        self.base = '{}account.post.ch'.format(self.protocol)
        self.swissid = '{}login.swissid.ch'.format(self.protocol)
        self.token_url = '{}postcardcreator.post.ch/saml/SSO/alias/defaultAlias'.format(self.protocol)
        self.user_agent = 'Mozilla/5.0 (Linux; Android 6.0.1; wv) ' + \
                          'AppleWebKit/537.36 (KHTML, like Gecko) ' + \
                          'Version/4.0 Chrome/52.0.2743.98 Mobile Safari/537.36'
        self.legacy_headers = {
            'User-Agent': self.user_agent
        }
        self.swissid_headers = {
            'User-Agent': self.user_agent
        }

        self.token = None
        self.token_type = None
        self.token_expires_in = None
        self.token_fetched_at = None
        self.cache_token = False
        self.refresh_token = None
        self.token_implementation = None

    def has_valid_credentials(self, username, password):
        try:
            self.authenticate_username_password(username, password)
            return True
        except PostcardCreatorException:
            return False

    def fetch_token_by_refresh_token(self, refresh_token: str, token_handler):
        try:
            access_token = self.post_refresh_token(refresh_token)
            logger.debug('swissid refresh_token authentication was successful')
        except Exception as e:
            logger.info("swissid refresh_token authentication failed")
            logger.info(e)
            raise e

        self.set_auth_info(access_token, token_handler)

    def authenticate_username_password(self, username, password) -> None:
        logger.debug('fetching postcard account token')

        if username is None or password is None:
            raise PostcardCreatorException('No username/ password given')

        logger.info("using swissid username password authentication")
        try:
            self.session = self._create_session()
            self._get_access_token_swissid(self.session, username, password)
            logger.debug('swissid username/password authentication was successful')
        except Exception as e:
            logger.info("swissid username password authentication failed")
            logger.info(e)
            raise e

    def set_auth_info(self, access_token: dict, token_handler):
        try:
            logger.debug(access_token)
            self.token = access_token['access_token']
            self.token_type = access_token['token_type']
            self.token_expires_in = access_token['expires_in']
            self.refresh_token = access_token['refresh_token']
            self.token_fetched_at = datetime.datetime.now()
            self.token_implementation = 'swissid'
            token_handler(access_token, self)
            logger.info("access_token successfully fetched")

        except Exception as e:
            logger.info("access_token does not contain required values. someting broke")
            raise e

    @staticmethod
    def _create_session(retries=5, backoff_factor=0.5, status_forcelist=(500, 502, 504)):
        # XXX: Backend will terminate connection if we request too frequently
        session = requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    @staticmethod
    def _get_code_verifier():
        return base64_encode(secrets.token_bytes(64))

    @staticmethod
    def _get_code(code_verifier):
        m = hashlib.sha256()
        m.update(code_verifier.encode('utf-8'))
        return base64_encode(m.digest())

    def _get_access_token_swissid(self, session, username, password) -> None:
        self.code_verifier = self._get_code_verifier()
        self.code_resp_uri = self._get_code(self.code_verifier)
        self.redirect_uri = 'ch.post.pcc://auth/1016c75e-aa9c-493e-84b8-4eb3ba6177ef'

        init_data = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'scope': 'PCCWEB offline_access',
            'response_mode': 'query',
            'state': 'abcd',
            'code_challenge': self.code_resp_uri,
            'code_challenge_method': 'S256',
            'lang': 'en'
        }
        url = 'https://pccweb.api.post.ch/OAuth/authorization?'
        resp = session.get(url + urllib.parse.urlencode(init_data),
                           allow_redirects=True,
                           headers=self.swissid_headers)
        _log_and_dump(resp)

        saml_payload = {
            'externalIDP': 'externalIDP'
        }
        url = 'https://account.post.ch/idp/?login' \
              '&targetURL=https://pccweb.api.post.ch/SAML/ServiceProvider/' \
              '?redirect_uri=' + self.redirect_uri + \
              '&profile=default' \
              '&app=pccwebapi&inMobileApp=true&layoutType=standard'
        resp = session.post(url,
                            data=saml_payload,
                            allow_redirects=True,
                            headers=self.swissid_headers)
        _log_and_dump(resp)
        if len(resp.history) == 0:
            raise PostcardCreatorException('fail to fetch ' + url)

        step1_goto_url = resp.history[len(resp.history) - 1].headers['Location']
        goto_param = re.search(r'goto=(.*?)$', step1_goto_url).group(1)
        try:
            goto_param = goto_param.split('&')[0]
        except Exception as e:
            # only use goto_param without further params
            pass
        logger.debug("goto parm=" + goto_param)
        if goto_param is None or goto_param == '':
            raise PostcardCreatorException('swissid: cannot fetch goto param')

        url = "https://login.swissid.ch/api-login/authenticate/token/status?locale=en&goto=" + goto_param + \
              "&acr_values=loa-1&realm=%2Fsesam&service=qoa1"
        resp = session.get(url, allow_redirects=True)
        _log_and_dump(resp)

        url = "https://login.swissid.ch/api-login/welcome-pack?locale=en" + goto_param + \
              "&acr_values=loa-1&realm=%2Fsesam&service=qoa1"
        resp = session.get(url, allow_redirects=True)
        _log_and_dump(resp)

        # login with username and password
        url = 'https://login.swissid.ch/api-login/authenticate/init?locale=en&goto=' + goto_param + \
              "&acr_values=loa-1&realm=%2Fsesam&service=qoa1"
        resp = session.post(url, allow_redirects=True)
        _log_and_dump(resp)

        # submit username and password
        self.url_query_string = "locale=en&goto=" + goto_param + \
                                "&acr_values=loa-1&realm=%2Fsesam&service=qoa1"

        url = "https://login.swissid.ch/api-login/authenticate/basic?" + self.url_query_string
        headers = self.swissid_headers
        auth_id = resp.json()['tokens']['authId']
        headers['authId'] = auth_id
        step_data = {
            'username': username,
            'password': password
        }
        resp = session.post(url, json=step_data, headers=headers, allow_redirects=True)
        _log_and_dump(resp)

        resp_json: dict = resp.json()
        if "errorCode" in resp_json and resp_json["errorCode"] == "INVALID_USERNAME_PASSWORD":
            raise PostcardCreatorException("failed to login, invalid username or password")

        self.next_action = resp_json['nextAction']['type']
        self.auth_id = resp_json['tokens']['authId']

    def finish_auth(self, token_handler):
        # anomaly detection
        session = self.session
        resp = self._swiss_id_anomaly_detection(self.session, self.auth_id, self.url_query_string)

        try:
            url = resp.json()['nextAction']['successUrl']
        except Exception as e:
            logger.info("failed to login. username/password wrong?")
            raise PostcardCreatorException("failed to login, username/password wrong?")

        resp = session.get(url, headers=self.swissid_headers, allow_redirects=True)
        _log_and_dump(resp)

        step7_soup = BeautifulSoup(resp.text, 'html.parser')
        url = step7_soup.find('form', {'name': 'LoginForm'})['action']
        resp = session.post(url, headers=self.swissid_headers)
        _log_and_dump(resp)

        # find saml response
        step7_soup = BeautifulSoup(resp.text, 'html.parser')
        saml_response = step7_soup.find('input', {'name': 'SAMLResponse'})

        if saml_response is None or saml_response.get('value') is None:
            raise PostcardCreatorException('Username/password authentication failed. Are your credentials valid?.')

        # prepare access token
        url = "https://pccweb.api.post.ch/OAuth/"  # important: '/' at the end
        customer_headers = self.swissid_headers
        customer_headers['Origin'] = 'https://account.post.ch'
        customer_headers['X-Requested-With'] = 'ch.post.it.pcc'
        customer_headers['Upgrade-Insecure-Requests'] = str(1)
        saml_payload = {
            'RelayState': step7_soup.find('input', {'name': 'RelayState'})['value'],
            'SAMLResponse': saml_response.get('value')
        }
        resp = session.post(url, headers=customer_headers,
                            data=saml_payload,
                            allow_redirects=False)  # do not follow redirects as we cannot redirect to android uri
        try:
            code_resp_uri = resp.headers['Location']
            init_data = parse_qs(urlparse(code_resp_uri).query)
            resp_code = init_data['code'][0]
        except Exception as e:
            print(e)
            raise PostcardCreatorException('response does not have code attribute: ' + url + '. Did endpoint break?')

        # get access token
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': resp_code,
            'code_verifier': self.code_verifier,
            'redirect_uri': self.redirect_uri,
        }
        url = 'https://pccweb.api.post.ch/OAuth/token'
        resp = requests.post(url,  # we do not use session here!
                             data=data,
                             headers=self.swissid_headers,
                             allow_redirects=False)
        _log_and_dump(resp)

        if 'access_token' not in resp.json() or resp.status_code != 200:
            raise PostcardCreatorException("not able to fetch access token: " + resp.text)

        self.set_auth_info(resp.json(), token_handler)

    def post_refresh_token(self, refresh_token: str):
        url = 'https://pccweb.api.post.ch/OAuth/token'
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }

        resp = requests.post(url, headers=self.swissid_headers, data=data)
        _log_and_dump(resp)

        json_resp = resp.json()

        if 'error' in json_resp:
            error = json_resp['error']
            if error == 'invalid_grant':
                raise PostcardCreatorTokenInvalidException(
                    "Token not valid anymore."
                )

        if 'access_token' not in resp.json() or resp.status_code != 200:
            raise PostcardCreatorException("not able to fetch access token: " + resp.text)

        return resp.json()

    def _swiss_id_anomaly_detection(self, session, auth_id_device_print, url_query_string):
        # XXX: Starting 2022-10, endpoints introduce anomaly detection, possibly to further restrict automated access
        # Currently, any valid device_print payload seems to work
        # useragent in request and payload can differ and still be valid
        url = 'https://login.swissid.ch/api-login/anomaly-detection/device-print?' + url_query_string
        try:
            next_action = self.next_action
            if next_action != 'SEND_DEVICE_PRINT':
                logger.warning('next action must be SEND_DEVICE_PRINT but got ' + next_action)

            device_print = self._formulate_anomaly_detection()
            headers = self.swissid_headers
            headers['authId'] = auth_id_device_print
            resp = session.post(url, json=device_print, headers=headers)
            _log_and_dump(resp)
        except Exception as e:
            msg = "Anomaly detection step failed. \n" \
                  + f"pending request: {url} \n"
            logger.info(msg)
            logger.info(e)
            raise PostcardCreatorException(msg, e)
        return resp

    def _formulate_anomaly_detection(self):
        # Valid device_print generated in an x86 android 12 emulator,
        # XXX: if something breaks in the future, we may have to get more clever here
        device_print = {
            "appCodeName": "Mozilla",
            "appName": "Netscape",
            "appVersion": self.user_agent.replace('Mozilla/', ''),  # Mozilla/5.0
            "fonts": {
                "installedFonts": "cursive;monospace;serif;sans-serif;fantasy;default;Arial;Courier;" + \
                                  "Courier New;Georgia;Tahoma;Times;Times New Roman;Verdana"
            },
            "language": "de",
            "platform": "Linux x86_64",
            "plugins": {
                "installedPlugins": ""
            },
            "product": "Gecko",
            "productSub": "20030107",
            "screen": {
                "screenColourDepth": 24,
                "screenHeight": 732,
                "screenWidth": 412
            },
            "timezone": {
                "timezone": -120
            },
            "userAgent": self.user_agent,
            "vendor": "Google Inc."
        }

        return device_print

    def to_json(self):
        return {
            'fetched_at': int(self.token_fetched_at.timestamp()),
            'token': self.token,
            'expires_in': self.token_expires_in,
            'type': self.token_type,
            'refresh_token': self.refresh_token,
            'implementation': self.token_implementation
        }

    def authenticate_mtan(self, code):
        url = "https://login.swissid.ch/api-login/authenticate/mtan?" + self.url_query_string
        data = {
            "code": code
        }
        headers = self.swissid_headers
        headers["authId"] = self.auth_id

        response = requests.post(url, headers=headers, json=data, verify=False)

        if response.status_code == 200:
            resp_json = response.json()
            self.next_action = resp_json['nextAction']['type']
            self.auth_id = resp_json['tokens']['authId']
            return response.json()
        else:
            response.raise_for_status()

    @staticmethod
    def _build_goto_url(path, params):
        query_string = urllib.parse.urlencode(params)
        return f"https://login.swissid.ch{path}?{query_string}"
