"""Install pinned official language data locally; system OCR tools stay external."""
import argparse
from pathlib import Path

import requests

ROOT=Path(__file__).resolve().parents[2]
REVISION='87416418657359cb625c412a48b6e1d6d41c29bd'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'outputs/tools/tessdata')
    args=parser.parse_args();args.directory.mkdir(parents=True,exist_ok=True)
    for language in ('eng','vie'):
        target=args.directory/(language+'.traineddata')
        if target.is_file() and target.stat().st_size:
            print(language+': already installed');continue
        url=f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{REVISION}/{language}.traineddata'
        with requests.get(url,timeout=(10,90),stream=True) as response:
            response.raise_for_status();payload=bytearray()
            for part in response.iter_content(65536):
                payload.extend(part)
                if len(payload)>30*1024*1024:raise ValueError('LANGUAGE_FILE_TOO_LARGE')
        if len(payload)<1000:raise ValueError('LANGUAGE_FILE_EMPTY')
        temporary=target.with_suffix('.download');temporary.write_bytes(payload);temporary.replace(target)
        print(language+': installed from official tessdata_fast '+REVISION)
    print('Tessdata: '+str(args.directory.resolve()))
    print('Tesseract and Poppler executables must also be installed; see docs/sprint4/LOCAL_DEMO.md.')


if __name__=='__main__':main()
