#!/usr/bin/python

import base64
import gzip
import pprint
import StringIO
import urllib
import urllib2

from google.protobuf import descriptor
from google.protobuf.internal.containers import RepeatedCompositeFieldContainer
import google.protobuf.message

import googleplay_pb2
from google.protobuf import text_format
from google.protobuf.message import DecodeError

class LoginError(Exception):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return repr(self.value)

class RequestError(Exception):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return repr(self.value)

class GooglePlayAPI(object):
  """Google Play Unofficial API Class
  Usual APIs methods are login(), search(), details(), download(), browse() and list().
  toStr() can be used to pretty print the result (protobuf object) of the previous methods.
  toDict() converts the result into a dict, for easier introspection.
  """

  SERVICE = "androidmarket"
  URL_LOGIN = "https://android.clients.google.com/auth" # "https://www.google.com/accounts/ClientLogin"
  ACCOUNT_TYPE_GOOGLE = "GOOGLE"
  ACCOUNT_TYPE_HOSTED = "HOSTED"
  ACCOUNT_TYPE_HOSTED_OR_GOOGLE = "HOSTED_OR_GOOGLE"
  PROTOCOL_VERSION = 2
  authSubToken = None
  context = None

  def __init__(self): # Search results may depend on the following parameters, so try to pick real ones.
    self.preFetch = {}
    
    self.androidId =  "xxxxxxxxxxxxxxxx" # change me
    

  def toDict(self, protoObj):
    """Converts the (protobuf) result from an API call into a dict, for easier introspection."""
    iterable = False
    if isinstance(protoObj, RepeatedCompositeFieldContainer):
      iterable = True
    else:
      protoObj = [protoObj]
    retlist = []

    for po in protoObj:
      msg = dict()
      for fielddesc, value in po.ListFields():
        #print value, type(value), getattr(value, '__iter__', False)
        if fielddesc.type == descriptor.FieldDescriptor.TYPE_GROUP or isinstance(value, RepeatedCompositeFieldContainer) or isinstance(value, google.protobuf.message.Message):
          msg[fielddesc.name] = self.toDict(value)
        else:
          msg[fielddesc.name] = value
      retlist.append(msg)
    if not iterable:
      if len(retlist) > 0:
        return retlist[0]
      else:
        return None
    return retlist
    
    
  def toStr(self, protoObj):
    """Used for pretty printing a result from the API."""
    return text_format.MessageToString(protoObj)
    
  def _try_register_preFetch(self, protoObj):
    fields = [i.name for (i,_) in protoObj.ListFields()]
    if("preFetch" in fields):
      for p in protoObj.preFetch:
        self.preFetch[p.url] = p.response


  def setAuthSubToken(self, authSubToken):
    self.authSubToken = authSubToken
    
    # Uncomment this line to print your auth token, and put it in config.py for faster access
    # print authSubToken

  def login(self, email=None, password=None, authSubToken = None):
    """Login to your Google Account. You must provide either:
    - an email and password
    - a valid Google authSubToken
    """
    if(authSubToken is not None):
      self.setAuthSubToken(authSubToken)
    else:
      if(email is None or password is None):
        raise Exception("You should provide at least authSubToken or (email and password)")
      params = {"Email": email, 
                "Passwd": password, 
                "service": self.SERVICE,
                "accountType": self.ACCOUNT_TYPE_HOSTED_OR_GOOGLE,
                "has_permission": "1",
                "source": "android",
                "androidId": self.androidId,
                "app": "com.android.vending",
                #"client_sig": self.client_sig,
                "device_country": "fr",
                "operatorCountry": "fr",
                "lang": "fr",
                "sdk_version": "16"}
      try:
        data = urllib2.urlopen(self.URL_LOGIN, urllib.urlencode(params)).read()
        data = data.split()
        params = {}
        for d in data:
          k, v = d.split("=")
          params[k.strip().lower()] = v.strip()
        if "auth" in params:
          self.setAuthSubToken(params["auth"])
        else:
          raise LoginError("Auth token not found.")
      except urllib2.HTTPError, e:
        if e.code == 403:
          data = e.fp.read().split()
          params = {}
          for d in data:
            k, v = d.split("=", 1)
            params[k.strip().lower()] = v.strip()
          if "error" in params:
            raise LoginError(params["error"])
          else:
            raise LoginError("Login failed.")
        else:
          raise e
        
  def executeRequestApi2(self, path, datapost=None):
  
    if(datapost is None and path in self.preFetch):
      data = self.preFetch[path]
    else:
      headers = { "Accept-Language": "fr-FR",
                  "Authorization": "GoogleLogin auth=%s" % self.authSubToken,
                  "X-DFE-Enabled-Experiments": "cl:billing.select_add_instrument_by_default",
                  "X-DFE-Unsupported-Experiments": "nocache:billing.use_charging_poller,market_emails,buyer_currency,prod_baseline,checkin.set_asset_paid_app_field,shekel_test,content_ratings,buyer_currency_in_app,nocache:encrypted_apk,recent_changes",
                  "X-DFE-Device-Id": self.androidId,
                  "X-DFE-Client-Id": "am-android-google",
                  #"X-DFE-Logging-Id": self.loggingId2,       # Deprecated?
                  "User-Agent": "Android-Finsky/3.7.13 (api=3,versionCode=8013013,sdk=16,device=crespo,hardware=herring,product=soju)",
                  "X-DFE-SmallestScreenWidthDp": "320",
                  "X-DFE-Filter-Level": "3",
                  "Host": "android.clients.google.com"}
                  
      if(datapost is not None):
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        
      request = urllib2.Request("https://android.clients.google.com/fdfe/%s" % path, datapost, headers)
      data = urllib2.urlopen(request).read()

    '''
    data = StringIO.StringIO(data)
    gzipper = gzip.GzipFile(fileobj=data)
    data = gzipper.read()
    '''
    message = googleplay_pb2.ResponseWrapper.FromString(data)
    self._try_register_preFetch(message)
    
    # Debug
    #print text_format.MessageToString(message)
    return message
    
  #####################################
  # Google Play API Methods
  #####################################
  
  def search(self, query, nb_results=None, offset=None):
    """Search for apps."""
    path = "search?c=3&q=%s" % urllib.quote_plus(query)   # TODO handle categories
    if(nb_results is not None):
      path += "&n=%d" % int(nb_results)
    if(offset is not None):
      path += "&o=%d" % int(offset)
      
    message = self.executeRequestApi2(path)
    return message.payload.searchResponse
    
  def details(self, packageName):
    """Get app details from a package name.
    packageName is the app unique ID (usually starting with 'com.')."""
    path = "details?doc=%s" % urllib.quote_plus(packageName)
    message = self.executeRequestApi2(path)
    return message.payload.detailsResponse
    
  def browse(self, cat=None, ctr=None):
    """Browse categories.
    cat (category ID) and ctr (subcategory ID) are used as filters."""
    path = "browse?c=3"
    if(cat != None):
      path += "&cat=%s" % urllib.quote_plus(cat)
    if(ctr != None):
      path += "&ctr=%s" % urllib.quote_plus(ctr)
    message = self.executeRequestApi2(path)
    return message.payload.browseResponse
    
  def list(self, cat, ctr=None, nb_results=None, offset=None):
    """List apps.
    If ctr (subcategory ID) is None, returns a list of valid subcategories.
    If ctr is provided, list apps within this subcategory."""
    path = "list?c=3&cat=%s" % urllib.quote_plus(cat)
    if(ctr != None):
      path += "&ctr=%s" % urllib.quote_plus(ctr)
    if(nb_results != None):
      path += "&n=%s" % urllib.quote_plus(nb_results)
    if(offset != None):
      path += "&o=%s" % urllib.quote_plus(offset)
    message = self.executeRequestApi2(path)
    return message.payload.listResponse
  
  
  def download(self, packageName, versionCode, offerType=1):
    """Download an app and return its raw data (APK file).
    packageName is the app unique ID (usually starting with 'com.').
    versionCode can be grabbed by using the details() method on the given app."""
    
    path = "purchase"
    data = "ot=%d&doc=%s&vc=%d" % (offerType, packageName, versionCode)
    message = self.executeRequestApi2(path, data)
    
    url = message.payload.buyResponse.purchaseStatusResponse.appDeliveryData.downloadUrl
    cookie = message.payload.buyResponse.purchaseStatusResponse.appDeliveryData.downloadAuthCookie[0]
    
    headers = {"Cookie" : "%s=%s" % (cookie.name, cookie.value),
               "User-Agent" : "AndroidDownloadManager/4.1.1 (Linux; U; Android 4.1.1; Nexus S Build/JRO03E)"}
    request = urllib2.Request(url, None, headers)
    data = urllib2.urlopen(request).read()
    return data
  
  
