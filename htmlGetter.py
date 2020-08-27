import urllib.request
import urllib.error
import codecs
import ssl
ssl._create_default_https_context = ssl._create_unverified_context


# urlからhtmlのソースを取得する
def get_html(url):
    req = urllib.request.Request(url, None, headers={
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:47.0) Gecko/20100101 Firefox/47.0",
    })
    res = urllib.request.urlopen(req)
    html = res.read()
    return codecs.decode(html, encoding='utf-8', errors='strict')
