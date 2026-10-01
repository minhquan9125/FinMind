"""Move legacy news JSON into daily folders without fetching network data."""
from stock_news_collector import DEFAULT_OUTPUT, SOURCE_OUTPUTS, read_articles, write_payload, output_lock
from news_storage import SCRAPERS, crawl_day, daily_path, migrate_daily


def main():
    inputs = [DEFAULT_OUTPUT, *SOURCE_OUTPUTS.values(), SCRAPERS / 'news_trial.json']
    expected = []
    for path in inputs:
        for article in read_articles(path).values():
            scopes = set(article.get('scopes', [])) | set(article.get('matched_symbols', [])) or {'market'}
            for scope in scopes:
                expected.append((daily_path(SCRAPERS, article['source'], scope,
                                            crawl_day(article['crawled_at'])), article))
    migrate_daily(SCRAPERS, inputs, read_articles, write_payload, output_lock)
    for path, original in expected:
        saved = read_articles(path, original['source'])[original['url']]
        for field, value in original.items():
            if field in ('symbols', 'matched_symbols', 'scopes', 'attachments'):
                assert set(value).issubset(saved.get(field, [])), (path, field)
            else:
                assert saved.get(field) == value, (path, original['url'], field)
    print(f'Verified {len(expected)} routed records against original data')
    for path in sorted({p for p, _ in expected}):
        print(f'{path.relative_to(SCRAPERS)}: {len(read_articles(path))} articles')


if __name__ == '__main__':
    main()
