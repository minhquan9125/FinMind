from news.news_storage import SCRAPERS

TEST_TMP = SCRAPERS / '.agent-state' / 'test-tmp'
TEST_TMP.mkdir(parents=True, exist_ok=True)
