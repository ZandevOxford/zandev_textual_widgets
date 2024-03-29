# Copyright ©️ 2024 John M Reynolds

import copy
import glob
import os
import os.path
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import rich.text
import textual.events as events
from textual import work
from textual.binding import Binding
from textual.containers import (
    Grid,
    Horizontal,
    ScrollableContainer,
    Vertical,
    VerticalScroll,
)
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

import platform

IS_WINDOWS = False

if platform.system() == "Windows":
    IS_WINDOWS = True
    import win32api


class Dialog(ModalScreen[str]):
    DEFAULT_CSS = """
    Dialog {
        align: center middle;
    }

    Dialog Vertical {
        width: 80%;
        height: auto;
        border: round $accent;
    }

    Dialog Horizontal {
        height: auto;
        border: round $primary-background;
    }

    Dialog Button {
        margin-left: 1;
        margin-right: 1;
    }

    Dialog Label {
        margin: 1;
    }

    """

    BINDINGS = [Binding(key="escape", action="app.pop_screen", description="Close")]

    label: str = ""
    buttons: List[Tuple[str, str, str]] = []

    def __init__(
        self,
        id: str,
        label: str = "",
        buttons: List[Tuple[str, str, str]] = [],
        **kwargs,
    ):
        super().__init__(**kwargs, id=id)
        self.label = label
        self.buttons = buttons

    def compose(self):
        yield Vertical(
            Label(self.label),
            Horizontal(
                *[
                    Button(button[0], id=button[1], variant=button[2])
                    for button in self.buttons
                ]
            ),
        )
        yield Footer()
        self.app.install_screen(self, self.id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)


size_scaling = [
    [1024 * 1024 * 1024 * 1024, "TiB"],
    [1024 * 1024 * 1024, "GiB"],
    [1024 * 1024, "MiB"],
    [1024, "KiB"],
]


def format_size(size: int) -> str:
    for scale in size_scaling:
        if size >= scale[0]:
            return f"{format(size / scale[0], '.2f')} {scale[1]}"
    return f"{size} B"


def format_last_modified(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).isoformat()[:19]


class DirTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        yield from (path for path in paths if os.path.isdir(path))


class SortLabel(Label):
    DEFAULT_CSS = """
        SortLabel {
            dock: right;
            width: 2;
            margin-right: 2;
        }
    """


class FileHeaderDrag(Label):
    DEFAULT_CSS = """
        FileHeaderDrag {
            dock: right;
            width: 1;
            background: $primary-background;
            margin-right: 1;
        }

        FileHeaderDrag:hover {
            background: $primary-background-lighten-2;
        }
    """

    drag_x: Optional[int] = None

    def __init__(self):
        super().__init__("↔")

    async def on_mouse_down(self, event: events.MouseDown):
        self.capture_mouse()

    async def on_mouse_up(self, event: events.MouseUp):
        self.capture_mouse(False)
        self.drag_done()

    def drag_done(self):
        self.drag_x = None
        self.parent.post_message(self.Resize(0, self.parent.index, done=True))

    class Resize(Message):
        def __init__(self, drag: int, index: int, done: bool):
            super().__init__()
            self.drag = drag
            self.index = index
            self.done = done

    async def on_mouse_move(self, event: events.MouseMove):
        if self.drag_x is not None:
            if not event.button:
                self.drag_done()
                return
            drag_x = event.screen_x - self.drag_x
            if drag_x:
                self.drag_x += drag_x
                self.parent.post_message(
                    self.Resize(drag_x, self.parent.index, done=False)
                )

    async def on_mouse_capture(self, event: events.MouseCapture):
        self.drag_x = event.mouse_position[0]


class FileHeaderColumn(Static):

    DEFAULT_CSS = """
        FileHeaderColumn {
            height: 1;
            width: auto;
        }
    """

    width = reactive(0)
    sort: Optional[bool] = reactive(None)
    index: int = 0
    up: Optional[Widget]
    down: Optional[Widget]
    label: str = ""

    def __init__(self, label: str, width: int, sort: Optional[bool], index: int):
        super().__init__(label)
        self.up = SortLabel("↑")
        self.down = SortLabel("↓")
        self.width = width
        self.index = index
        self.sort = sort
        self.label = label

    def render(self):
        return rich.text.Text(self.label, overflow="crop", no_wrap=True)

    def compose(self):
        yield self.up
        yield self.down
        yield FileHeaderDrag()

    def watch_width(self, width):
        self.styles.width = width

    def watch_sort(self):
        sort = self.sort
        self.up.styles.visibility = "visible" if sort else "hidden"
        self.down.styles.visibility = (
            "visible" if sort is not None and not sort else "hidden"
        )

    class Clicked(Message):
        def __init__(self, index: int):
            super().__init__()
            self.index = index

    async def on_click(self, message):
        self.post_message(self.Clicked(self.index))


DEFAULT_COLUMNS = [
    {"name": "Name", "width": 100},
    {"name": "Size", "width": 15, "desc": True},
    {"name": "Last modified", "width": 30, "desc": True},
]


class FileHeader(Widget):

    DEFAULT_CSS = """
        FileHeader {
            height: 1;
            background: $accent-darken-1;
            dock: top;
        }
    """

    columns: List = []
    sort: Tuple[int, bool] = reactive([0, True])

    def __init__(self, default_columns=List[Dict]):
        super().__init__()
        self.columns = copy.deepcopy(default_columns)

        for index, column in enumerate(self.columns):
            sort = None if self.sort[0] != index else self.sort[1]
            widget = FileHeaderColumn(
                column["name"], column["width"], sort=sort, index=index
            )
            column["widget"] = widget

    def compose(self):
        yield Horizontal(*(column["widget"] for column in self.columns))
        self._update_self_width()

    def get_width(self) -> int:
        return sum(column["width"] for column in self.columns)

    def _update_self_width(self):
        self.styles.width = self.get_width()

    async def _update_width(self, drag, index):
        width = max(self.columns[index]["width"] + drag, 5)
        self.columns[index]["width"] = width
        self.columns[index]["widget"].width = width
        self._update_self_width()

    class Sort(Message):
        def __init__(self, sort: Tuple[int, bool]):
            super().__init__()
            self.sort = sort

    def watch_sort(self):
        for index, column in enumerate(self.columns):
            if column.get("widget"):
                column["widget"].sort = None if index != self.sort[0] else self.sort[1]
        self.post_message(self.Sort(self.sort))

    async def on_file_header_column_clicked(self, event: FileHeaderColumn.Clicked):
        if self.sort[0] == event.index:
            self.sort = (self.sort[0], not self.sort[1])
        else:
            self.sort = (event.index, not self.columns[event.index].get("desc", False))


class FileColumn(Widget):

    text: Optional[rich.text.Text] = reactive(None)

    def __init__(self):
        super().__init__()

    def render(self):
        return self.text

    def _update(
        self,
        width: int,
        height: int,
        scroll: int,
        columns: List[Dict],
        formatter: Callable[[Dict], str],
    ):
        text = rich.text.Text(overflow="ellipsis", no_wrap=True)
        for column in columns:
            line = formatter(column).replace("\n", "") + "\n"
            styles = []
            if column.get("hover"):
                styles.append("underline")
            if column.get("selected"):
                styles.append("bold")
            if column.get("focus"):
                styles.append("on white")
            if column.get("dir"):
                styles.append("italic")
            text.append(line, style=" ".join(styles))
        self.text = text

        self.styles.width = width
        self.styles.height = height
        self.styles.offset = (scroll, 0)


class FileList(Widget):

    DEFAULT_CSS = """
        FileList {
            overflow: scroll scroll;
        }

        FileList Vertical.fit {
            height: auto;
        }

        FileList Horizontal.file {
            dock: top;
            margin-top: 1;
            background: $background-darken-1;
        }

        FileList Vertical.dummy {
            height: auto;
            background: blue;
            visibility: hidden;
        }

    """

    directory: Optional[str] = None
    filter: Optional[str] = None
    container: Optional[Widget] = None
    header: Optional[FileHeader] = None
    dummy_container: Optional[Vertical] = None
    files: List[Dict] = []
    filename_column: Optional[FileColumn] = None
    size_column: Optional[FileColumn] = None
    modified_column: Optional[FileColumn] = None
    virtual_scroll_x: int = 0
    virtual_scroll_y: int = 0
    sort: Tuple[int, bool] = reactive([0, True])
    last_hover: Optional[int] = None
    show_dirs: bool = False
    show_files: bool = True

    can_focus = True
    key_index: Optional[int] = reactive(None)

    async def watch_scroll_x(self, old_value: float, new_value: float) -> None:
        self.virtual_scroll_x = int(new_value)
        self.header.styles.offset = (-self.scroll_x, 0)
        self.update_file_list()
        return super().watch_scroll_x(old_value, new_value)

    async def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        self.virtual_scroll_y = int(new_value)
        self.update_file_list()
        return super().watch_scroll_y(old_value, new_value)

    def update(self, directory: str, filter: str):
        self.directory = directory
        self.filter = filter
        self.run_worker(self._update, exclusive=True)

    def __init__(self):
        super().__init__()
        default_columns = copy.deepcopy(DEFAULT_COLUMNS)
        default_columns[0]["width"] = int(self.app.size.width * 0.70 - 49)
        self.header = FileHeader(default_columns)
        self.container = Horizontal(classes="file")
        self.dummy_container = Vertical(classes="dummy")
        self.dummy_container.styles.width = self.header.get_width()

        self.filename_column = FileColumn()
        self.size_column = FileColumn()
        self.modified_column = FileColumn()

        self.container.mount(self.filename_column)
        self.container.mount(self.size_column)
        self.container.mount(self.modified_column)

    def compose(self):
        yield self.header
        yield self.container
        yield self.dummy_container

    async def on_file_header_drag_resize(self, event: FileHeaderDrag.Resize):
        if event.drag:
            await self.header._update_width(event.drag, event.index)
            self.update_file_list()
        self.dummy_container.styles.width = self.header.get_width()

    async def on_resize(self, event):
        self.update_file_list()

    def on_file_header_sort(self, event: FileHeader.Sort):
        self.sort = event.sort

    def watch_sort(self):
        old_index = self.key_index
        if old_index is not None:
            try:
                self.files[old_index]["focus"] = False
            except:
                pass
        self.sort_files()
        if old_index is not None:
            try:
                self.files[0]["focus"] = True
            except:
                pass
        self.scroll_y = 0.0
        self.update_file_list()

    def sort_files(self):
        if self.sort[0] == 0:
            self.files = sorted(
                self.files, key=lambda x: x["filename"], reverse=not self.sort[1]
            )
        elif self.sort[0] == 1:
            self.files = sorted(
                self.files,
                key=lambda x: (x["size"], x["filename"]),
                reverse=not self.sort[1],
            )
        elif self.sort[0] == 2:
            self.files = sorted(
                self.files,
                key=lambda x: (x["modified"], x["filename"]),
                reverse=not self.sort[1],
            )

    async def on_mouse_move(self, event: events.MouseMove):
        new_index: Optional[int] = None
        row = event.get_content_offset(self.container)
        if row is not None:
            new_index = row[1] + self.virtual_scroll_y
        if new_index != self.last_hover:
            try:
                self.files[self.last_hover]["hover"] = False
            except:
                pass
            self.last_hover = new_index
            try:
                self.files[new_index]["hover"] = True
            except:
                pass
            self.update_file_list()

    def update_file_list(self):
        max_height = self.content_size.height - 2
        self.dummy_container.styles.height = len(self.files) - max_height
        self.container.styles.width = self.header.get_width()
        self.container.styles.height = max_height
        fileinfo = self.files[
            self.virtual_scroll_y : self.virtual_scroll_y + max_height
        ]
        self.filename_column._update(
            self.header.columns[0]["width"],
            max_height,
            -self.virtual_scroll_x,
            fileinfo,
            lambda x: x["filename"],
        )
        self.size_column._update(
            self.header.columns[1]["width"],
            max_height,
            -self.virtual_scroll_x,
            fileinfo,
            lambda x: format_size(x["size"]) if not x.get("dir") else "",
        )
        self.modified_column._update(
            self.header.columns[2]["width"],
            max_height,
            -self.virtual_scroll_x,
            fileinfo,
            lambda x: format_last_modified(x["modified"]),
        )

    async def _update(self):
        directory = self.directory
        filter = self.filter

        files = []
        dirs = []
        path = os.path.join(directory, filter)
        for pathname in glob.iglob(path):
            basename = os.path.basename(pathname)
            if self.show_files:
                if os.path.isfile(pathname):
                    files.append(basename)
            if self.show_dirs:
                if os.path.isdir(pathname):
                    dirs.append(basename)
        fileinfo = []
        for basename in files:
            size = 0
            modified = 0
            path = os.path.join(directory, basename)
            try:
                modified = os.path.getmtime(path)
                size = os.path.getsize(path)
            except OSError:
                pass
            fileinfo.append({"filename": basename, "size": size, "modified": modified})
        for basename in dirs:
            modified = 0
            path = os.path.join(directory, basename)
            try:
                modified = os.path.getmtime(path)
            except OSError:
                pass
            fileinfo.append(
                {"filename": basename, "size": 0, "modified": modified, "dir": True}
            )

        self.files = fileinfo
        self.sort_files()
        self.update_file_list()

    class FileSelected(Message):
        def __init__(self, index: int):
            self.index = index
            super().__init__()

    async def on_click(self, event: events.Click):
        row = event.get_content_offset(self.container)
        if row is not None:
            index = row[1] + self.virtual_scroll_y
            if index >= len(self.files):
                return
            self.post_message(self.FileSelected(index))
            self.key_index = index

    def clip_key_index(self, index: int):
        return max(min(index, len(self.files) - 1), 0)

    def clip_virtual_index(self, index: int):
        return max(min(index, len(self.files) - self.size.height + 2), 0)

    def watch_key_index(self, old_index, new_index):
        scroll = False
        if old_index == new_index:
            return
        if old_index is not None:
            try:
                self.files[old_index]["focus"] = False
            except:
                pass
        if new_index is None:
            self.update_file_list()
            return
        try:
            self.files[new_index]["focus"] = True
        except:
            pass
        overflow = new_index - self.virtual_scroll_y
        if overflow < 0:
            self.virtual_scroll_y = self.clip_virtual_index(
                self.virtual_scroll_y + overflow
            )
            scroll = True
        else:
            overflow = new_index - self.virtual_scroll_y - self.size.height + 3
            if overflow > 0:
                self.virtual_scroll_y = self.clip_virtual_index(
                    self.virtual_scroll_y + overflow
                )
                scroll = True
        if scroll:
            if self.last_hover is not None:
                try:
                    self.files[self.last_hover]["hover"] = False
                except:
                    pass
            self.scroll_y = float(self.virtual_scroll_y)
        self.update_file_list()

    async def on_focus(self):
        if self.key_index is not None:
            return
        self.key_index = self.clip_key_index(self.virtual_scroll_y)

    async def on_blur(self):
        self.key_index = None

    async def on_key(self, event: Key):
        if event.key in ("enter", "space"):
            if self.key_index is not None:
                self.post_message(self.FileSelected(self.key_index))
            event.stop()
        elif event.key in ("down", "up"):
            self.key_index = self.clip_key_index(
                self.key_index + (1 if event.key == "down" else -1)
            )
        elif event.key in ("pageup", "pagedown"):
            self.key_index = self.clip_key_index(
                self.key_index
                + (self.size.height - 2) * (1 if event.key == "pagedown" else -1)
            )


class Filter(Input):
    DEFAULT_CSS = """
    Filter {
        width: 6;
    }
    """


class DirGrid(Grid):
    pass


class FileGrid(Grid):
    pass


class DirUp(Button):
    DEFAULT_CSS = """
        DirUp {
            min-width: 1;
            width: 3;
            height: 3;
            margin: 0;
        }
    """

    def __init__(self):
        super().__init__("↑")


class SelectDrive(Button):
    DEFAULT_CSS = """
        SelectDrive {
            margin-left: 1;
            margin-right: 0;
            margin-top: 0;
            margin-bottom: 0;
            min-width: 1;
            width: 4;
            height: 3;
        }
    """

    def __init__(self):
        super().__init__("PC")


class PathSeparator(Static):
    DEFAULT_CSS = """
        PathSeparator {
            width: 1;
            background: $secondary-background-darken-2;
            height: 1;
        }
    """


class PathLabel(Label):
    DEFAULT_CSS = """
        PathLabel {
            background: $secondary-background;
            text-style: none;
        }

        PathLabel:hover {
            background: $accent;
            text-style: none;
        }

        PathLabel.Invalid {
            background: $error;
        }

        PathLabel.Terminal {
            background: $secondary-background-lighten-2;
        }

        PathLabel.Terminal:hover {
            background: $accent-lighten-2;
        }
    """

    class PathClicked(Message):
        widget: Widget

        def __init__(self, widget):
            self.widget = widget
            super().__init__()

    path: str = ""

    def __init__(self, path: str, valid=True, terminal=False):
        super().__init__(path)
        self.path = path
        if not valid:
            self.add_class("Invalid")
        if terminal:
            self.add_class("Terminal")

    async def on_click(self, event: events.Click):
        self.post_message(self.PathClicked(self))
        event.stop()


class PathInput(Input):

    path_control: Optional[Widget] = None

    def __init__(self, value: str, path_control: Widget):
        super().__init__(value)
        self.path_control = path_control

    class PathEdited(Message):
        pass

    async def on_blur(self, event):
        self.post_message(self.PathEdited())

    async def on_key(self, event: Key):
        if event.key == "enter":
            event.stop()
            self.path_control.focus()


class UpdatePath(Message):
    def __init__(self, path: str):
        super().__init__()
        self.path = path


class DriveSelect(ModalScreen[str]):
    DEFAULT_CSS = """
    DriveSelect {
        align: center middle;
    }

    DriveSelect Vertical {
        width: 80%;
        height: auto;
        border: round $accent;
    }

    DriveSelect Horizontal {
        height: auto;
        border: round $primary-background;
    }

    DriveSelect Button {
        margin-left: 1;
        margin-right: 1;
    }

    DriveSelect Label {
        margin: 1;
    }

    """
    AUTO_FOCUS = "ListView"
    BINDINGS = [Binding(key="escape", action="app.pop_screen", description="Close")]

    def get_drives(self) -> List[str]:
        if IS_WINDOWS:
            drives = win32api.GetLogicalDriveStrings()
            drives = drives.split("\000")[:-1]
            return drives
        return []

    def compose(self):
        drives = self.get_drives()
        drive_list = ListView(*(ListItem(Label(name), name=name) for name in drives))
        yield Vertical(
            Label("Select drive"),
            VerticalScroll(drive_list),
            Button("Cancel"),
        )
        yield Footer()

    async def on_list_view_selected(self, event: ListView.Selected):
        self.dismiss(event.item.name)

    async def on_button_pressed(self, event):
        self.dismiss()


class PathControl(ScrollableContainer):

    DEFAULT_CSS = """
        PathControl {
            layout: horizontal;
            overflow-x: auto;
            overflow-y: hidden;
        }

        PathControl Horizontal {
            align-vertical: middle;
            background: $secondary-background-darken-2;
            margin: 0;
            width: auto;
            min-width: 100%;
            height: 3;
        }

        PathControl Horizontal.Internal {
            border: none red;
            padding-left: 2;
        }

        PathControl PathInput {
            width: auto;
            min-width: 100%;
        }

        PathControl Button {
            width: 4;
        }

    """

    class PathChanged(Message):
        pass

    path: str = ""
    valid_path: str = ""
    base_path: str = ""
    input_widget: Optional[Input] = None
    directory_area: Optional[Horizontal] = None
    can_focus = True

    def __init__(self):
        super().__init__()

    def switch_widget(self, input_visible: bool = False):
        self.input_widget.styles.display = "block" if input_visible else "none"
        self.input_widget.disabled = not input_visible
        self.directory_area.styles.display = "none" if input_visible else "block"
        self.directory_area.disabled = bool(input_visible)

    def edit_mode(self):
        self.switch_widget(True)
        self.input_widget.focus()

    async def populate_directory_area(self, test=False):
        if not self.directory_area:
            return
        await self.directory_area.remove_children()
        dirs = []
        path = self.path
        filename = "dummy"
        while path and filename:
            path, filename = os.path.split(path)
            if filename:
                dirs.append(filename)
        if path:
            dirs.append(path)
        built_path = ""
        self.valid_path = ""
        to_mount = []
        for directory in reversed(dirs):
            built_path = os.path.join(built_path, directory)
            valid = os.path.isdir(built_path)
            if valid:
                self.valid_path = built_path
            to_mount.append(
                [directory, valid, valid and self.base_path == built_path, True]
            )
        for index in range(1, len(to_mount)):
            mount = to_mount[index]
            if not mount[1] and to_mount[index - 1][1]:
                to_mount[index - 1][2] = True
        if to_mount:
            to_mount[-1][3] = False
        for mount in to_mount:
            self.directory_area.mount(PathLabel(mount[0], mount[1], mount[2]))
            if mount[0] != os.path.sep and mount[3]:
                self.directory_area.mount(PathSeparator(os.path.sep))

    def compose(self):
        self.input_widget = PathInput(self.path, self)
        self.directory_area = Horizontal(classes="Internal")
        self.switch_widget(False)
        self.populate_directory_area()

        yield Horizontal(self.directory_area, self.input_widget)

    async def on_update_path(self, event: UpdatePath):
        await self.update_path(event.path)

    async def update_path(self, path: str, notify=True, add=False):
        path = os.path.abspath(os.path.expanduser(path))
        self.path = path
        if not add:
            self.base_path = path
        if self.input_widget:
            self.input_widget.value = path
        await self.populate_directory_area(test=True)
        if notify:
            self.post_message(self.PathChanged())

    async def on_path_input_path_edited(self, event):
        await self.update_path(self.input_widget.value)
        self.switch_widget(False)

    async def on_path_label_path_clicked(self, event: PathLabel.PathClicked):
        path = ""
        for widget in self.directory_area.children:
            if type(widget) == PathLabel:
                path = os.path.join(path, widget.path)
            if widget == event.widget:
                break
        await self.update_path(path)
        event.stop()

    async def on_click(self, event: events.Click):
        self.edit_mode()


class Divider(Label):

    DEFAULT_CSS = """
        Divider {
            width: 1;
            height: 100%;
            background: $primary-background;
            content-align-vertical: middle;
        }

        Divider:hover {
            background: $primary-background-lighten-2;

        }
    """

    drag_x: Optional[int] = None

    def __init__(self):
        super().__init__("↔")

    async def on_mouse_down(self, event: events.MouseDown):
        self.capture_mouse()

    async def on_mouse_up(self, event: events.MouseUp):
        self.capture_mouse(False)
        self.drag_x = None

    class Resize(Message):
        def __init__(self, divider, drag_x):
            super().__init__()
            self.divider = divider
            self.drag_x = drag_x

    async def on_mouse_move(self, event: events.MouseMove):
        if self.drag_x is not None:
            if not event.button:
                self.drag_x = None
                return
            drag_x = event.screen_x - self.drag_x
            if drag_x:
                self.drag_x += drag_x
                self.parent.post_message(self.Resize(self, drag_x))

    async def on_mouse_capture(self, event: events.MouseCapture):
        self.drag_x = event.mouse_position[0]


class FileSelectorMode(Enum):
    EXISTING = 1
    NEW = 2
    DIRECTORY = 3


class FilterInput(Input):

    class Confirm(Message):
        pass

    async def on_blur(self, event):
        self.post_message(self.Confirm())

    async def on_key(self, event: Key):
        if event.key == "enter":
            self.post_message(self.Confirm())
            event.stop()


class FileSelector(ModalScreen):

    BINDINGS = [Binding(key="escape", action="screen.close", description="Close")]

    AUTO_FOCUS = "FileGrid Input"

    DEFAULT_CSS = """
        FileSelector {
            align: center middle;
        }

        FileSelector Grid {
            width: 95%;
            height: 95%;
            grid-size: 1 3;
            grid-columns: 100%;
            grid-rows: 3 1fr 8;
            border: blank green;
            background: $background-lighten-1;
            align-vertical: middle;
        }

        FileSelector Input {
            border: round $accent;
            width: 100%;
        }

        FileSelector DirGrid {
            margin: 1 0 1 0;
            width: 100%;
            height: 100%;
            grid-size: 3 1;
            grid-columns: 1fr 1 3fr;
            grid-rows: 100%;
            border: none;
            background: $panel;
        }

        FileSelector FileGrid {
            margin: 0;
            width: 100%;
            height: 100%;
            grid-size: 4 2;
            grid-columns: 8 1fr auto auto;
            grid-rows: 3 3;
            border: blank red;
            background: $panel;
        }

        FileSelector FileGrid Button {
            margin-left: 1;
            margin-right: 1;
            align-vertical: bottom;
            row-span: 2;
        }

        FileSelector FileGrid Label {
            align-vertical: bottom;
            background: $panel-lighten-1;
            
            text-align: right;
        }

        FileSelector .Middle {
            align-vertical: middle;
        }

        FileSelector .Double {
            row-span: 2;
        }

        FileSelector .TopGrid {
            margin: 0;
            width: 100%;
            height: 100%;
            grid-size: 3 1;
            grid-columns: 3 1fr 6;
            grid-rows: 3;
            border: none;
            background: $panel;
        }

        FileSelector .TopGridWindows {
            margin: 0;
            width: 100%;
            height: 100%;
            grid-size: 4 1;
            grid-columns: 3 5 1fr 6;
            grid-rows: 3;
            border: none;
            background: $panel;
        }

        FileSelector Input.valid {
            color: green;
        }
    """

    mode: FileSelectorMode = FileSelectorMode.EXISTING
    directory: str = ""
    multi_select: bool = False
    directory_select: bool = False
    filter: str = ""
    ok_button: Optional[Widget] = None
    cancel_button: Optional[Widget] = None
    directory_input: Optional[Input] = None
    files_input: Optional[Input] = None
    files_label: Optional[Input] = None
    filter_input: Optional[Input] = None
    filter_label: Optional[Input] = None
    divider: Optional[Widget] = None
    dirgrid: Optional[Widget] = None
    dir_width = reactive(30)
    filename: str = ""
    directory_tree: Optional[DirTree] = None
    ok_text: str = ""
    show_all: bool = False

    def __init__(
        self,
        directory: str,
        mode: FileSelectorMode = FileSelectorMode.EXISTING,
        show_all: bool = False,
        filename: str = "",
        ok_text: str = "Open",
        filter: str = "*",
    ):
        super().__init__()
        self.mode = mode
        self.filename = filename
        self.directory = directory
        self.filter = filter
        self.ok_text = ok_text
        self.show_all = show_all

    def watch_dir_width(self):
        self.dirgrid.styles.grid_columns = f"{self.dir_width} 1 1fr"

    def on_divider_resize(self, event: Divider.Resize):
        self.dir_width += event.drag_x

    def compose(self):
        self.directory_input = PathControl()
        self.directory_input.post_message(UpdatePath(self.directory))
        self.file_list = FileList()
        if self.mode == FileSelectorMode.DIRECTORY:
            self.file_list.show_dirs = True
            if not self.show_all:
                self.file_list.show_files = False
        else:
            if self.show_all:
                self.file_list.show_dirs = True
        self.files_input = Input(self.filename)
        self.files_label = Label("File")
        self.filter_input = FilterInput(value=self.filter)
        self.filter_label = Label("Type")

        if self.mode == FileSelectorMode.DIRECTORY:
            self.files_input.styles.visibility = "hidden"
            self.files_label.styles.visibility = "hidden"
            self.filter_input.styles.visibility = "hidden"
            self.filter_label.styles.visibility = "hidden"

        self.ok_button = Button(self.ok_text, variant="success")
        self.cancel_button = Button("Cancel", variant="error")
        self.file_list.update(self.directory_input.path, self.filter_input.value)
        self.directory_tree = DirTree(self.directory)
        self.divider = Divider()
        self.dirgrid = DirGrid(self.directory_tree, self.divider, self.file_list)
        self.dir_width = int(self.app.size.width / 4)

        top_grid = Grid(
            classes="TopGrid" if not IS_WINDOWS else "TopGridWindows",
        )
        top_grid.mount(DirUp())
        if IS_WINDOWS:
            top_grid.mount(SelectDrive())
        top_grid.mount_all(
            (
                self.directory_input,
                Button("Edit", classes="DirEdit"),
            )
        )
        yield Grid(
            top_grid,
            self.dirgrid,
            FileGrid(
                Vertical(self.files_label, classes="Middle"),
                self.files_input,
                Vertical(self.ok_button, classes="Middle Double"),
                Vertical(self.cancel_button, classes="Middle Double"),
                Vertical(self.filter_label, classes="Middle"),
                self.filter_input,
            ),
        )
        yield Footer()

    def commit(self):
        self.dismiss(os.path.join(self.directory_input.path, self.files_input.value))

    def cancel(self):
        self.dismiss("")

    async def on_button_pressed(self, event: Button.Pressed):
        button = event.button
        if button == self.ok_button:
            self.commit()
        elif button == self.cancel_button:
            self.cancel()
        elif "DirEdit" in button.classes:
            self.directory_input.edit_mode()
        elif type(button) == DirUp:
            await self.directory_input.update_path(
                os.path.dirname(self.directory_input.path)
            )
            await self.path_changed()
        elif type(button) == SelectDrive:

            async def drive_callback(drive):
                if drive:
                    await self.directory_input.update_path(
                        drive, notify=False, add=False
                    )
                    await self.path_changed()

            self.app.push_screen(DriveSelect(), callback=drive_callback)

    async def path_changed(self):
        self.directory_tree.path = self.directory_input.valid_path
        self.directory_tree.reload()
        self.file_list.directory = self.directory_input.valid_path
        self.file_list.filter = self.filter_input.value
        await self.file_list._update()

    async def on_key(self, event: Key) -> None:
        current_item = self.app.focused
        if event.key in ("enter"):
            if current_item == self.files_input:
                self.commit()

    async def on_filter_input_confirm(self, event):
        self.file_list.filter = self.filter_input.value
        await self.file_list._update()

    async def update_dir(self, path):
        await self.directory_input.update_path(str(path), notify=False, add=True)
        self.file_list.directory = self.directory_input.path
        if self.mode == FileSelectorMode.EXISTING:
            self.files_input.value = ""
        self.file_list.filter = self.filter_input.value

    async def on_directory_tree_directory_selected(self, event):
        await self.update_dir(str(event.path))
        await self.file_list._update()

    async def on_path_control_path_changed(self, event: PathControl.PathChanged):
        await self.path_changed()

    def action_close(self):
        self.cancel()

    async def on_file_list_file_selected(self, event: FileList.FileSelected):
        try:
            fileinfo = self.file_list.files[event.index]
            if fileinfo.get("dir"):
                path = os.path.join(self.directory_input.path, fileinfo["filename"])
                await self.update_dir(path)
                await self.path_changed()
            else:
                self.files_input.value = fileinfo["filename"]
                self.file_list.update_file_list()
        except:
            pass
