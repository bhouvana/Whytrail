# whytrail-scrapy

Logs a `whytrail` explanation whenever a spider callback raises, via
Scrapy's own `spider_error` signal.

```python
class MySpider(scrapy.Spider):
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        import whytrail_scrapy
        whytrail_scrapy.install(crawler.signals)
        return spider
```

Includes which URL's response the callback was parsing when it failed.
The response body itself is never captured by this plugin.
