"""Portable connection helper for task 1/2 operator scripts; never logs secrets."""
import os
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[2]
def dsn():
 value=os.environ.get('DATABASE_URL') or dotenv_values(ROOT/'backend/.env',interpolate=False).get('DATABASE_URL')
 if not value:raise RuntimeError('Set DATABASE_URL in backend/.env or process environment')
 u=urlsplit(value)
 if not u.username or not u.password or not u.path.strip('/'):raise ValueError('DATABASE_URL requires database credentials and database name')
 host=os.environ.get('FINMIND_TUNNEL_HOST','127.0.0.1');port=int(os.environ.get('FINMIND_TUNNEL_PORT','15433'))
 return urlunsplit((u.scheme,u.netloc.rsplit('@',1)[0]+'@'+host+':'+str(port),u.path,u.query,u.fragment))
