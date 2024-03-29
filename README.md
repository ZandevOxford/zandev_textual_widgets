# Zandev Textual Widgets

This is a collection of widgets for
[Textual](https://github.com/Textualize/textual/tree/main)
with a focus on aiding writing apps which look and function more like
desktop apps.

## Installation

Install with

```
pip install zandev_textual_widgets
```

or just copy the code to your project.

Dependencies are just textual, and pywin32 if you are running on
Windows.

## Example

See `testapp.py` as a simple example.

## Widgets

### Cascading drop down menus

This is a system of drop down menus intended to replace the Textual
Header Widget with typical desktop app menus.

Alternatively (or in addition), these can be triggered in a pop-up
mode for example for context menus.

As is common on destop menus, navigation is by one of individual
click, click and release or keyboard, but only one navigation mode
will be active at once.

#### Usage

Create a screen from MenuScreen and add it to your App, e.g:

```
    SCREENS = {
        "menu": MenuScreen(),
    }
```

The MenuScreen should exist for the lifetime of your app, and
contains menus for all of your screens which are dynamically
displayed as needed.

For each menu, create a Menu containing MenuItem children, e.g.:

```
    app_menu = Menu(
        MenuItem(name="About", menu_action="screen.about"),
        MenuItem(name="Quit", menu_action="screen.quit"),
        id="app_menu",
    )
    menu_screen.mount(app_menu)
```

The menu_action is the Textual action to trigger. Alternatively
you can provide a callback which will be called with the menu item
name and action, e.g.:

```
    MenuItem(
        name="callback_test", menu_action="callback_test", callback=my_callback
    ),
```

To add a spacer to the menu, add a disabled MenuItem.

To add a menu bar to a screen, add a MenuBar to your screen containing
MenuHeader children insead of the standard Textual Header, with menu_id
being the id of the menu to open, e.g. in the compose
method:

```
    yield MenuBar(
        MenuHeader(name="TestApp", menu_id="app_menu"),
        MenuHeader(name="File", menu_id="file_menu"),
    )
```

To add a sub-menu, in a MenuItem, give a menu_action with a name
which is "menu." followed by the id of the sub-menu, e.g:

```
    sub_item = MenuItem(name="More...", menu_action="menu.more_menu")
```

To trigger the keyboard navigation mode of the menu bar, call the
activate method of MenuBar, e.g.:

```
    self.menu_bar.activate()
```

To trigger a single menu as a pop-up, call the context_menu method of the
MenuScreen, with the id of the target menu, the Offset of the position to
place the menu and whether it is in keyboard navigation mode, e.g.:

```
    await self.app.get_screen("menu").context_menu(
        "test_menu", Offset(widget.region.x, widget.region.y), key=True
    )
```

### File selector

This provides a modal file selector similar in style to the Windows one.

Features include:

 * Filtering by type.
 * Selection of parent directories by clicking on path elements.
 * Directory navigation by tree.
 * Resizable file area (by dragging).
 * Resizable and sortable columns in the file area.

#### Usage

Create a FileSelector screen and trigger is as a standard Textual modal
dialog, e.g.:

```
    self.app.push_screen(FileSelector(directory=os.getcwd()), callback=file_result)
```

The return is the absolute path of the selection.

The parameters to the FileSelector constructor are:

 * `mode`: one of the FileSelectorMode enum values: EXISTING to allow selection
   of an existing file (e.g. for an open), NEW to allow naming of a new file
   (e.g. for a save as), and DIRECTORY to allow navigation to a directory but
   not selection of a file.
 * `filename`: the initial name of a file.
 * `directory`: the initial directory to start in.
 * `filter`: the initial filter glob (defaults to `*`).
 * `ok_text`: what to name the confirmation button, e.g. Open or Save.
 * `show_all`: by default, only files or directories are shown in the file
   area dependent on mode. Set this to True to show both.

### Simple dialog

This is a simple modal dialog for quick confirmation or informational
dialogs.

#### Usage

Create a Dialog with an id, a label and a list of tuples of (button id,
button name, variant) of buttons, e.g.:

```
quit_dialog = Dialog(
    id="quit_dialog",
    label="Quit application?",
    buttons=[("Quit", "quit", "error"), ("Cancel", "cancel", "primary")],
)
```

Then trigger this as a standard Textual modal dialog, e.g.:

```
    self.app.push_screen(quit_dialog, check_quit)
```
