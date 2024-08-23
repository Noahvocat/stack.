import gi
import os
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
from Xlib import X, display, Xatom
import Xlib.protocol.event

class TaskbarWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Taskbar")
        self.set_default_size(800, 30)  # Initial size; will be overridden
        self.set_position(Gtk.WindowPosition.NONE)
        self.connect("destroy", Gtk.main_quit)
        
        self.box = Gtk.Box(spacing=6)
        self.add(self.box)

        # Connect to X 11 display
        self.disp = display.Display()
        self.screen = self.disp.screen()
        self.root = self.screen.root

        self.set_type_hint(Gdk.WindowTypeHint.DOCK)

        self.connect("realize", self.on_realize)
        
        # Listen for property change events on the root window
        self.root.change_attributes(event_mask=X.PropertyChangeMask)
        GLib.timeout_add(100, self.check_for_events)

    def on_realize(self, widget):
        screen_width = self.screen.width_in_pixels
        taskbar_height = 30
        self.set_size_request(screen_width, taskbar_height)
        self.move(0, 0)
        self.set_strut_properties(screen_width, taskbar_height)
        
        self.refresh_taskbar() 

    def set_strut_properties(self, screen_width, taskbar_height):
        gdk_window = self.get_window()
        window_id = gdk_window.get_xid()

        top_strut = taskbar_height

        # _NET_WM_STRUT_PARTIAL
        strut_partial = [
            0,                # left
            0,                # right
            top_strut,        # top
            0,                # bottom
            0,                # left_start_y
            0,                # left_end_y
            0,                # right_start_y
            0,                # right_end_y
            0,                # top_start_x
            screen_width - 1, # top_end_x
            0,                # bottom_start_x
            0                 # bottom_end_x
        ]

        # _NET_WM_STRUT
        strut = [0, 0, top_strut, 0]

        # Setting properties on the taskbar window
        window = self.disp.create_resource_object('window', window_id)
        window.change_property(self.disp.intern_atom('_NET_WM_STRUT_PARTIAL'), Xatom.CARDINAL, 32, strut_partial)
        window.change_property(self.disp.intern_atom('_NET_WM_STRUT'), Xatom.CARDINAL, 32, strut)
        self.disp.sync()

    def refresh_taskbar(self):
        dropdown_menu = Gtk.Menu()
        self.box.foreach(Gtk.Widget.destroy)

        startbtn = Gtk.Image.new_from_file("/etc/stackde/startico.png")
#the start menu might be fucked up after my additions and i aint fixing that shit
        # Create a MenuButton for the dropdown and set the image
        menu_button = Gtk.MenuButton()
        menu_button.set_image(startbtn)
        menu_button.set_popup(dropdown_menu)
        self.box.pack_start(menu_button, False, False, 0)  # Pack at the start (left)

        # Apps button
        apps_item = Gtk.MenuItem(label="Apps")
        apps_item.connect("activate", self.open_rofi_drun)
        dropdown_menu.append(apps_item)

        # Run button
        run_item = Gtk.MenuItem(label="Run")
        run_item.connect("activate", self.open_rofi_run)
        dropdown_menu.append(run_item)
#shit doesnt work cuz power menu not implemented yet
        # Power button
        power_item = Gtk.MenuItem(label="Power")
        power_item.connect("activate", self.open_power_program)
        dropdown_menu.append(power_item)

        dropdown_menu.show_all()

        # Get the taskbar window ID
        taskbar_window_id = self.get_window().get_xid()

        # Get list of windows
        window_ids = self.root.get_full_property(self.disp.intern_atom('_NET_CLIENT_LIST'), Xatom.WINDOW).value

        for win_id in window_ids:
            if win_id == taskbar_window_id:
                continue  # Skip the taskbar window itself

            win = self.disp.create_resource_object('window', win_id)
            win_name = win.get_wm_name()
            win_class = win.get_wm_class()
            win_type = win.get_full_property(self.disp.intern_atom('_NET_WM_WINDOW_TYPE'), Xatom.ATOM)

            print(f"Window ID: {win_id}, Name: {win_name}, Class: {win_class}, Type: {win_type}")

            if win_type:
                win_type_names = [self.disp.get_atom_name(atom) for atom in win_type.value]
                print(f"Window types: {win_type_names}")

            if win_type and self.disp.intern_atom('_NET_WM_WINDOW_TYPE_NORMAL') not in win_type.value:
                print(f"Skipping non-normal window type: {win_type}")
                continue  # Skip non-normal window types

            if win_name:
                button = Gtk.Button(label=win_name)
                button.connect("clicked", self.on_button_click, win_id)
                self.box.pack_start(button, True, True, 0)

        self.box.show_all()

    def open_rofi_drun(self, widget):
        os.system("rofi -show drun")

    def open_rofi_run(self, widget):
        os.system("rofi -show run")

    def open_power_program(self, widget):
        os.system("python /etc/droplet/power.py")

    def on_button_click(self, button, win_id):
        win = self.disp.create_resource_object('window', win_id)

        # Check if the window is minimized (_NET_WM_STATE_HIDDEN)
        wm_state = win.get_full_property(self.disp.intern_atom('_NET_WM_STATE'), Xatom.ATOM)
        if wm_state and self.disp.intern_atom('_NET_WM_STATE_HIDDEN') in wm_state.value:
            print(f"Window {win_id} is minimized, requesting to show it.")
            # Request the window to be shown (unminimized)
            self.root.change_property(
                self.disp.intern_atom('_NET_WM_STATE'),
                Xatom.ATOM,
                32,
                [self.disp.intern_atom('_NET_WM_STATE_REMOVE'), self.disp.intern_atom('_NET_WM_STATE_HIDDEN'), 0, 1, 0],
                X.PropModeReplace
            )

        # Request to activate the window
        data = [2, X.CurrentTime, win_id, 0, 0]
        event = Xlib.protocol.event.ClientMessage(window=self.root, client_type=self.disp.intern_atom('_NET_ACTIVE_WINDOW'), data=(32, data))
        self.root.send_event(event, event_mask=X.SubstructureNotifyMask | X.SubstructureRedirectMask)
        self.disp.flush()
        print(f"Sent activation request for window {win_id}.")

    def check_for_events(self):
        while self.disp.pending_events():
            event = self.disp.next_event()
            if event.type == X.PropertyNotify:
                print(f"PropertyNotify event received for atom: {event.atom}")
                if event.atom == self.disp.intern_atom('_NET_CLIENT_LIST'):
                    self.refresh_taskbar()
        return True

def main():
    taskbar = TaskbarWindow()
    taskbar.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
