"""Start the local demo using the existing private operator configuration."""
import os
import sys
from pathlib import Path

import uvicorn
from demo_environment import load_demo_environment

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))


def main():
    os.chdir(BACKEND)
    load_demo_environment(BACKEND)
    uvicorn.run('src.main:app',host='127.0.0.1',port=8000)


if __name__=='__main__':main()
