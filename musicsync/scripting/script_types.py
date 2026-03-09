from abc import abstractmethod
from dataclasses import dataclass, field
from enum import auto
from typing import ClassVar
import xml.etree.ElementTree as et
from xml.etree.ElementTree import Element

from musicsync.xml_object import XmlObject
from musicsync.utils import GuiStrEnum


class ScriptType(GuiStrEnum):
    DOWNLOAD = 'DownloadScript', 'Download script', ''
    METADATA_SUGGESTIONS = 'MetadataSuggestionsScript', 'Metadata suggestions script', ''

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

        cls = ScriptType(el.tag).cls
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

    def __hash__(self):
        return hash(self.name)


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

    def __hash__(self):
        return super().__hash__()


class DownloadScriptWhen(GuiStrEnum):
    PRE_PROCESS = auto(), 'Pre-process', 'Called once per video, after yt-dlp extracted the info dict, and before the video passes the download filter (i.e. it will be executed for Tracks with action "Download" or "Redownload metadata").'
    AFTER_FILTER = auto(), 'After filter', 'Called once per video, after the video passes the download filter (i.e. it will only be executed for Tracks with action "Download" that weren\'t filtered by a "Pre-process" script).'
    VIDEO = auto(), 'Video', 'Called once per requested format for each video, after format selection'
    BEFORE_DL = auto(), 'Before download', 'Called once per requested format for each video, after output templates (e.g. for the filename) have been evaluated, and before the download starts'
    POST_PROCESS = auto(), 'Post-process', 'Called once per requested format for each video, after the download finished. Now the URL type and final filepath is available'
    AFTER_MOVE = auto(), 'After move', 'Called once per requested format for each video, after the file has been moved to its final location'
    AFTER_VIDEO = auto(), 'After video', 'Called once per video, after all requested formats of the video have been downloaded'
    PLAYLIST = auto(), 'Playlist', 'Called once at the end of downloading a playlist-type URL. Contains metadata about the playlist and all its entries'


@dataclass
class DownloadScript(Script):
    when: DownloadScriptWhen = DownloadScriptWhen.POST_PROCESS

    script_type: ClassVar[ScriptType] = ScriptType.DOWNLOAD

    def __post_init__(self):
        if isinstance(self.when, str):
            self.when = DownloadScriptWhen(self.when)

    def update_xml_attrs(self, attrs) -> str:
        pass

    def __hash__(self):
        return super().__hash__()