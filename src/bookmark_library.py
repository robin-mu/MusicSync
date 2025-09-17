import os
import sqlite3
from dataclasses import dataclass, field
from typing import Union
import pandas as pd
import json

@dataclass
class Bookmark:
    url: str
    bookmark_title: str
    page_title: str

@dataclass
class BookmarkFolder:
    title: str
    children: list[Bookmark] = field(default_factory=list)

@dataclass
class BookmarkLibrary:
    children: list[Union['Bookmark', 'BookmarkFolder']] = field(default_factory=list)

    @staticmethod
    def create_from_path(path: str) -> 'BookmarkLibrary':
        if 'firefox' in path.lower():
            return FirefoxLibrary.from_path(path)
        elif 'opera' in path.lower():
            return OperaLibrary.from_path(path)
        raise ValueError('This browser is not supported')

class FirefoxLibrary(BookmarkLibrary):
    @staticmethod
    def from_path(path) -> 'FirefoxLibrary':
        if not os.path.isfile(path):
            raise FileNotFoundError(f'File {path} not found')
        connection = sqlite3.connect(path)
        bookmarks = pd.read_sql('SELECT b.id AS id, b.type AS type, b.parent AS parent, '
                                'b.title AS bookmark_title, p.url AS url, p.title AS page_title FROM moz_bookmarks AS b '
                                'LEFT JOIN moz_places AS p ON b.fk=p.id', connection, index_col='id')

        folders: dict[int, BookmarkFolder] = {}
        for row in bookmarks.itertuples():
            if row.type == 1:
                new_entry = Bookmark(url=row.url, bookmark_title=row.bookmark_title, page_title=row.page_title)
            elif row.type == 2:
                new_entry = BookmarkFolder(title=row.bookmark_title)
                folders[row.Index] = new_entry
            else:
                continue

            if row.parent != 0:
                folders[row.parent].children.append(new_entry)

        return FirefoxLibrary(children=list(folders.values()))


class OperaLibrary(BookmarkLibrary):
    @staticmethod
    def from_path(path) -> 'OperaLibrary':
        with open(path, 'r', encoding='utf8') as f:
            file = json.load(f)
        # TODO

if __name__ == '__main__':
    BookmarkLibrary.create_from_path('/home/robin/.mozilla/firefox/dpv2usmq.default-release/places.sqlite')