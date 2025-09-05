from xml.etree.ElementTree import Element

from PySide6.QtGui import QStandardItemModel, QStandardItem

import xml.etree.ElementTree as et

class Folder(QStandardItem):
    def __init__(self, name):
        super().__init__()
        self.setText(name)

    def to_element(self):
        return et.Element("Folder", name=self.text())


class Collection(QStandardItem):
    def __init__(self, name: str, folder_path: str='', filename_format: str='', file_extension: str='',
                 metadata_fields=None, save_playlists_to_subfolders: bool=False):
        super().__init__()
        if metadata_fields is None:
            metadata_fields = []
        self.setText(name)

        self.folder_path = folder_path
        self.filename_format = filename_format
        self.file_extension = file_extension
        self.metadata_fields = metadata_fields

        if isinstance(save_playlists_to_subfolders, str):
            self.save_playlists_to_subfolders = save_playlists_to_subfolders == 'True'
        else:
            self.save_playlists_to_subfolders = save_playlists_to_subfolders

    def to_element(self):
        return et.Element("Collection", name=self.text(), folder_path=self.folder_path,
                          filename_format=self.filename_format, file_extension=self.file_extension,
                          metadata_fields=','.join(self.metadata_fields),
                          save_playlists_to_subfolders=str(self.save_playlists_to_subfolders))


class FoldersTreeModel(QStandardItemModel):
    def __init__(self, xml_file=None):
        super(FoldersTreeModel, self).__init__()

        self.root = self.invisibleRootItem()

        if xml_file is not None:
            tree = et.parse(xml_file)
            xml_root = tree.getroot()
            self.build_tree(self.root, xml_root)

    def build_tree(self, parent: QStandardItem, children: Element):
        for child in children:
            if child.tag == 'Folder':
                new_folder = Folder(child.attrib['name'])
                parent.appendRow(new_folder)
                self.build_tree(new_folder, child)
            elif child.tag == 'Collection':
                new_collection = Collection(**child.attrib)
                parent.appendRow(new_collection)

    def to_xml(self, filename):
        xml_root = et.Element('MusicSyncFolders')

        def append(parent: Element, children: QStandardItem):
            for i in range(children.rowCount()):
                row = children.child(i)
                new_element = row.to_element()
                append(new_element, row)
                parent.append(new_element)

        append(xml_root, self.root)
        et.ElementTree(xml_root).write(filename)

    @staticmethod
    def add_folder(parent: Folder):
        new_folder = Folder('')
        parent.appendRow(new_folder)
        return new_folder

    @staticmethod
    def add_collection(parent: Folder):
        new_collection = Collection('')
        parent.appendRow(new_collection)
        return new_collection