# AutoZone Data Router

MVP benchmark for testing AutoZone ZIP/store-localized product data across multiple scraping providers.

## Frozen test case

- Product URL: https://www.autozone.com/p/duralast-disc-brake-pad-set-mkd619/97471
- Product: Duralast Disc Brake Pad Set MKD619
- AutoZone product ID: 97471
- ZIP: 90001
- Expected store: #5425, 1457 E Florence, Los Angeles, CA 90001

## Required fields

- product_name
- part_number
- price
- availability

## Optional fields

- brand
- images
- description
- fitment
- pickup_available
- ship_available
- store_id
- delivery_estimate

## Providers

1. Scrape.do
2. ScraperAPI
3. ZenRows
4. ScrapingAnt
5. Firecrawl
6. ScrapingBee
7. MrScraper
8. Spider Cloud
9. Thunderbit
10. Parsera
11. Social Crawl

## Validation rule

A provider is considered successful only when the mandatory product data is valid and the requested ZIP/store context is verified. Missing optional fields do not cause a retry.

## Security

Provider credentials must never be committed. Use GitHub Actions Secrets for CI and environment variables for local development if needed. Rotate any API keys that have previously been exposed.
