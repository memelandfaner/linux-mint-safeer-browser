import os,re
from pathlib import Path
import xml.etree.ElementTree as ET
r=Path(__file__).resolve().parents[1]
v=(r/'packaging/VERSION').read_text().strip()
assert re.fullmatch(r'\d+\.\d+\.\d+(?:[.+~-][\w.-]+)?',v),v
assert re.search(r'APP_VERSION = "'+re.escape(v)+r'"',(r/'safeer_mint.py').read_text()),'APP_VERSION differs'
assert ET.parse(r/'io.github.memelandfaner.SafeerBrowser.metainfo.xml').find('releases/release').get('version')==v,'AppStream version differs'
if os.environ.get('GITHUB_REF_TYPE')=='tag':
    assert os.environ['GITHUB_REF_NAME']=='v'+v,'Release tag differs'
print('Version:',v)
