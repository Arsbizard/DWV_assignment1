from twisted.internet import reactor, defer
from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
import scrapy
import re
import sqlite3
import json

def clean_text(text_list):
    """
    Очищает текст, сохраняя пробелы между словами.
    """
    cleaned_elements = []
    for text in text_list:
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        if text and not any(char in text for char in ["mw-parser-output", "{", "}", "[", "]", "1", "2", "3", "4", "5", "6", "7", "8", "9"]):
            cleaned_elements.append(text)
    return ", ".join(cleaned_elements) if cleaned_elements else "N/A"


class HighestGrossingFilmsSpider(scrapy.Spider):
    name = "highest_grossing_films"
    start_urls = ["https://en.wikipedia.org/wiki/List_of_highest-grossing_films"]

    def parse(self, response):
        table = response.xpath("(//table[contains(@class,'wikitable')])[1]")
        rows = table.xpath(".//tr")[1:]

        for row in rows:
            rank = row.xpath("./td[1]/text()").get()
            title = row.xpath(".//th/i/a/text() | .//th/span/i/a/text()").get()
            box_office = row.xpath(".//td[3]/text()").get()
            box_office = re.sub(r"[^\d.]", "", box_office) if box_office else "N/A"
            year = row.xpath(".//td[4]/text()").get()
            relative_link = row.xpath("./th/i/a/@href | ./th/span/i/a/@href").get()

            if title and relative_link:
                movie_url = response.urljoin(relative_link)
                yield response.follow(movie_url, self.parse_movie_details, meta={
                    'rank': rank.strip() if rank else "N/A",
                    'title': title.strip(),
                    'url': movie_url,
                    'box_office': box_office.strip(),
                    'year': year.strip() if year else "N/A"
                })

    def parse_movie_details(self, response):
        movie_details = {
            "Rank": response.meta['rank'],
            "Title": response.meta['title'],
            "Release Year": response.meta['year'],
            "Box Office Revenue": response.meta['box_office'],
            "URL": response.meta['url']
        }

        directors = response.xpath("//table[contains(@class, 'infobox')]//th[contains(text(), 'Directed by')]/following-sibling::td//text()[normalize-space() and not(parent::sup)]").getall()
        movie_details["Directed by"] = clean_text(directors)

        countries = response.xpath("//table[contains(@class, 'infobox')]//th[contains(text(), 'Country') or contains(text(), 'Countries')]/following-sibling::td//text()[normalize-space() and not(parent::sup)]").getall()
        movie_details["Country of origin"] = clean_text(countries)

        yield movie_details

configure_logging()
runner = CrawlerRunner({
    "FEEDS": {
        "films_data.json": {
            "format": "json",
            "encoding": "utf8",
            "indent": 4,
            "overwrite": True
        }
    },
    "LOG_LEVEL": "WARNING"
})


@defer.inlineCallbacks
def crawl():
    yield runner.crawl(HighestGrossingFilmsSpider)
    reactor.stop()


crawl()
reactor.run()

import sqlite3
import json

with open("films_data.json", "r", encoding="utf-8") as file:
    films_data = json.load(file)
conn = sqlite3.connect("films.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS films (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    release_year INTEGER,
    director TEXT,
    box_office REAL,
    country TEXT
)
""")

for film in films_data:
    cursor.execute("""
    INSERT INTO films (title, release_year, director, box_office, country)
    VALUES (?, ?, ?, ?, ?)
    """, (
        film.get("Title"),
        film.get("Release Year"),
        film.get("Directed by"),
        float(film.get("Box Office Revenue", 0)),
        film.get("Country of origin")
    ))

conn.commit()
conn.close()
