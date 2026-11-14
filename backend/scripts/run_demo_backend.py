"""Start the local demo using the existing private operator configuration."""
import os
import sys
from pathlib import Path

import uvicorn
from dotenv import dotenv_values

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))


def main():
    os.chdir(BACKEND)
    value=dotenv_values(BACKEND/'.env.operator',interpolate=False).get('DATABASE_URL')
    if value:
        os.environ.setdefault('ADMIN_INGEST_DATABASE_URL',value)
    uvicorn.run('src.main:app',host='127.0.0.1',port=8000)


if __name__=='__main__':main()
