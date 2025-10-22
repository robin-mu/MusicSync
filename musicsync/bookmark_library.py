import os
import sqlite3
from dataclasses import dataclass, field
from typing import Union

import pandas as pd


@dataclass
class Bookmark:
    id: str
    parent: Union['BookmarkFolder', 'BookmarkLibrary'] = field(repr=False)
    url: str
    bookmark_title: str
    page_title: str

@dataclass
class BookmarkFolder:
    id: str
    parent: Union['BookmarkFolder', 'BookmarkLibrary'] = field(repr=False)
    title: str
    children: dict[str, Union['Bookmark', 'BookmarkFolder']] = field(default_factory=dict, repr=False)

    def get_all_bookmarks(self) -> dict[str, 'Bookmark']:
        flattened = {}
        for child in self.children.values():
            if isinstance(child, BookmarkFolder):
                flattened.update(child.get_all_bookmarks())
            elif isinstance(child, Bookmark):
                flattened[child.id] = child

        return flattened


@dataclass
class BookmarkLibrary:
    children: dict[int | str, Union['Bookmark', 'BookmarkFolder']] = field(default_factory=dict)

    @staticmethod
    def create_from_path(path: str) -> 'BookmarkLibrary':
        if 'firefox' in path.lower():
            return FirefoxLibrary.from_path(path)
        raise ValueError('This browser is not supported')

    def go_to_path(self, id_path: list[str]) -> Union['BookmarkFolder', 'Bookmark']:
        cursor = self
        for id in id_path:
            cursor = cursor.children[id]

        return cursor

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
        library = FirefoxLibrary()
        for row in bookmarks.itertuples():
            parent = folders[row.parent] if row.parent != 0 else library
            if row.type == 1:
                new_entry = Bookmark(id=str(row.Index), parent=parent, url=row.url, bookmark_title=row.bookmark_title, page_title=row.page_title)
            elif row.type == 2:
                new_entry = BookmarkFolder(id=str(row.Index), parent=parent, title=row.bookmark_title)
                folders[row.Index] = new_entry
            else:
                continue

            if row.parent != 0:
                folders[row.parent].children[new_entry.id] = new_entry
            else:
                library.children = {new_entry.id: new_entry}

        return library
