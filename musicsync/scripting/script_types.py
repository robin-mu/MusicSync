from abc import abstractmethod
from dataclasses import dataclass, field
from enum import auto
from typing import ClassVar
import xml.etree.ElementTree as et
from xml.etree.ElementTree import Element

from musicsync.xml_object import XmlObject
from musicsync.utils import GuiStrEnum


class ScriptType(GuiStrEnum):
    DOWNLOAD = auto(), 'Download script', ''
    METADATA_SUGGESTIONS = auto(), 'Metadata suggestions', ''

    @property
    def cls(self):
        if self == ScriptType.METADATA_SUGGESTIONS:
            return MetadataSuggestionsScript
        elif self == ScriptType.DOWNLOAD:
            return DownloadScript

        return None



@dataclass
class Script(XmlObject):
    name: str
    script: str = ''

    enabled: bool = field(default=False, compare=False, repr=False)
    script_type: ClassVar[ScriptType] = None

    @staticmethod
    def from_xml(el: Element) -> 'XmlObject':
        script = '\n'.join(' ' * int(c.attrib.get('indent', 0)) + (c.text or '') for c in el)
        cls = None
        if el.tag == 'MetadataSuggestionsScript':
            cls = MetadataSuggestionsScript
        elif el.tag == 'DownloadScript':
            cls = DownloadScript

        if cls is None:
            raise AttributeError('Unknown Script type')

        return cls(**(el.attrib | {'script': script}))

    def to_xml(self) -> Element:
        attrs = vars(self).copy()
        attrs.pop('enabled')
        attrs.pop('script')
        self.update_xml_attrs(attrs)

        el = et.Element(self.__class__.__name__, attrib=attrs)
        for line in self.script.split('\n'):
            line = line.replace('\t', ' ' * 10)
            indent = len(line) - len(line.lstrip(' '))
            line_el = et.Element('ScriptLine', indent=str(indent))
            line_el.text = line.lstrip(' ')
            el.append(line_el)

        return el

    @abstractmethod
    def update_xml_attrs(self, attrs) -> str:
        pass

@dataclass
class MetadataSuggestionsScript(Script):
    field_name: str = ''
    timed_data: bool = False
    show_format_options: bool = False
    default_format_as_title: bool = False
    default_remove_brackets: bool = False
    local_field: bool = False
    overwrite_metadata_table: bool = False

    script_type: ClassVar[ScriptType] = ScriptType.METADATA_SUGGESTIONS

    def __post_init__(self):
        if isinstance(self.timed_data, str):
            self.timed_data = self.timed_data == 'True'
        if isinstance(self.show_format_options, str):
            self.show_format_options = self.show_format_options == 'True'
        if isinstance(self.default_format_as_title, str):
            self.default_format_as_title = self.default_format_as_title == 'True'
        if isinstance(self.default_remove_brackets, str):
            self.default_remove_brackets = self.default_remove_brackets == 'True'
        if isinstance(self.local_field, str):
            self.local_field = self.local_field == 'True'
        if isinstance(self.overwrite_metadata_table, str):
            self.overwrite_metadata_table = self.overwrite_metadata_table == 'True'

    def update_xml_attrs(self, attrs) -> str:
        attrs['timed_data'] = str(self.timed_data)
        attrs['show_format_options'] = str(self.show_format_options)
        attrs['default_format_as_title'] = str(self.default_format_as_title)
        attrs['default_remove_brackets'] = str(self.default_remove_brackets)
        attrs['local_field'] = str(self.local_field)
        attrs['overwrite_metadata_table'] = str(self.overwrite_metadata_table)


class DownloadScriptWhen(GuiStrEnum):
    PRE_PROCESS = auto(), 'Pre-process', 'After yt-dlp extracted the info dict, before the video passes the download filter (i.e. this script will be executed for Tracks with action "Download" or "Redownload metadata").'
    AFTER_FILTER = auto(), 'After filter', 'After the Track passes yt-dlp\'s filter. This script will only be executed for Tracks with action "Download" that weren\'t filtered by a "Pre-process" script.'
    VIDEO = auto(), 'Video', ''
    BEFORE_DL = auto(), 'Before download', ''
    POST_PROCESS = auto(), 'Post-process', ''
    AFTER_MOVE = auto(), 'After move', ''
    AFTER_VIDEO = auto(), 'After video', ''
    PLAYLIST = auto(), 'Playlist', ''


@dataclass
class DownloadScript(Script):
    when: DownloadScriptWhen = DownloadScriptWhen.POST_PROCESS

    script_type: ClassVar[ScriptType] = ScriptType.DOWNLOAD

    def __post_init__(self):
        if isinstance(self.when, str):
            self.when = DownloadScriptWhen(self.when)

    def update_xml_attrs(self, attrs) -> str:
        pass