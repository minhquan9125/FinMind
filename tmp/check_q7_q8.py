import asyncio, os, sys, asyncpg, uuid
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv('.env')

async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require')
    
    # Q07
    uid7 = uuid.UUID('87e842c1-9a34-51b5-addb-f0715d5adeca')
    r7 = await conn.fetchrow("SELECT article_id, title, published_at, source, symbols, content FROM public.news_articles WHERE article_id = $1", uid7)
    if r7:
        print('=== Q07 FOUND ===')
        print('Title:', r7['title'])
        print('Date:', r7['published_at'], 'Source:', r7['source'])
        print('Symbols:', r7['symbols'])
        print('Content snippet:\n', r7['content'][:400])
        print('Contains 35.730,97:', '35.730,97' in r7['content'])
        print('Contains 35.431:', '35.431' in r7['content'])
        print('Contains 106.593:', '106.593' in r7['content'])
    else:
        print('=== Q07 NOT FOUND ===')

    # Q08
    uid8 = uuid.UUID('c8e13429-c236-5a5d-859f-068b890ef5ed')
    r8 = await conn.fetchrow("SELECT article_id, title, published_at, source, symbols, content FROM public.news_articles WHERE article_id = $1", uid8)
    if r8:
        print('\n=== Q08 FOUND ===')
        print('Title:', r8['title'])
        print('Date:', r8['published_at'], 'Source:', r8['source'])
        print('Symbols:', r8['symbols'])
        print('Content snippet:\n', r8['content'][:400])
        print('Contains 3.200:', '3.200' in r8['content'])
        print('Contains 3.206:', '3.206' in r8['content'])
        print('Contains Setra:', 'Setra' in r8['content'])
        print('Contains 1.202:', '1.202' in r8['content'])
        print('Contains Bonday:', 'Bonday' in r8['content'])
        print('Contains 2.004:', '2.004' in r8['content'])
        print('Contains 789:', '789' in r8['content'])
    # Q05
    uid5 = uuid.UUID('d56ce227-22e1-5ba0-8595-7cc1879bf95e')
    r5 = await conn.fetchrow("SELECT article_id, title, published_at, source, symbols, content FROM public.news_articles WHERE article_id = $1", uid5)
    if r5:
        print('\n=== Q05 (doc 1) ===')
        print('Title:', r5['title'])
        print('Date:', r5['published_at'], 'Source:', r5['source'])
        print('Symbols:', r5['symbols'])
        for kw in ['13.500', 'VietinBank', '27%', '12.800', 'Vietcombank', '14%', '10.000']:
            print(f'  Contains {kw}:', kw in r5['content'])
        for line in r5['content'].split('.'):
            if any(k in line for k in ['13.500', '12.800']):
                print('  Matched line:', line.strip())

    uid5_2 = uuid.UUID('e38b8a58-7bad-5f19-b318-593c066302ed')
    r5_2 = await conn.fetchrow("SELECT article_id, title, published_at, source, symbols, content FROM public.news_articles WHERE article_id = $1", uid5_2)
    if r5_2:
        print('\n=== Q05 (doc 2) ===')
        print('Title:', r5_2['title'])
        print('Date:', r5_2['published_at'], 'Source:', r5_2['source'])
        print('Symbols:', r5_2['symbols'])
        for kw in ['13.500', 'VietinBank', '27%', '12.800', 'Vietcombank', '14%', '10.000']:
            print(f'  Contains {kw}:', kw in r5_2['content'])
        for line in r5_2['content'].split('.'):
            if any(k in line for k in ['13.500', '12.800']):
                print('  Matched line:', line.strip())

    await conn.close()

asyncio.run(check())
