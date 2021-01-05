#NOTE: This ONLY works for Windows atm

#Whether Monika can use notifications or not
default persistent._mas_enable_notifications = False

#Whether notification sounds are enabled or not
default persistent._mas_notification_sounds = True

#Whether Monika can see your active window or not
default persistent._mas_windowreacts_windowreacts_enabled = False

#Persistent windowreacts db
default persistent._mas_windowreacts_database = dict()

#A global list of events we DO NOT want to unlock on a new session
default persistent._mas_windowreacts_no_unlock_list = list()

#A dict of locations where notifs are used, and if they're enabled for said location
default persistent._mas_windowreacts_notif_filters = dict()

init -10 python in mas_windowreacts:
    #We need this in case we cannot get access to the libs, so everything can still run
    can_show_notifs = True

    #If we don't have access to the required libs to do windowreact related things
    can_do_windowreacts = True

    #The windowreacts db
    windowreact_db = {}

    #Group list, to populate the menu screen
    #NOTE: We do this so that we don't have to try to get a notification
    #In order for it to show up in the menu and in the dict
    _groups_list = [
        "Topic Alerts",
        "Window Reactions",
    ]

init python in mas_windowreacts:
    import os
    import store
    #The initial setup

    #We can only do this on windows
    if renpy.windows:
        #We need to extend the sys path to see our packages
        import sys
        sys.path.append(renpy.config.gamedir + '\\python-packages\\')

        #We try/catch/except to make sure the game can run if load fails here
        try:
            #Going to import win32gui for use in destroying notifs
            import win32gui
            #Import win32api so we know if we can or cannot use notifs
            import win32api

            #Since importing the required libs was successful, we can move onto importing and initializing a balloontip
            import balloontip

            #And finally, import the internal functions to make getting window handle easier
            from win32gui import GetWindowText, GetForegroundWindow

            #Now we initialize the notification class
            __tip = balloontip.WindowsBalloonTip()

            #Now we set the hwnd of this temporarily
            __tip.hwnd = None

        except:
            #If we fail to import, then we're going to have to make sure nothing can run.
            can_show_notifs = False
            can_do_windowreacts = False

            #Log this
            store.mas_utils.writelog("[WARNING]: win32api/win32gui failed to be imported, disabling notifications.\n")

    elif renpy.linux:
        #Get session type
        session_type = os.environ.get("XDG_SESSION_TYPE")

        #Wayland is not supported, disable wrs
        if session_type == "wayland":
            can_show_notifs = False
            can_do_windowreacts = False
            store.mas_utils.writelog("[WARNING]: Wayland is not yet supported, disabling notifications.\n")

        #X11 however is fine
        elif session_type == "x11":
            try:
                import Xlib

                from Xlib.display import Display
                from Xlib.error import BadWindow

                __display = Display()
                __root = display.screen().root

            except ImportError:
                can_show_notifs = False
                can_do_windowreacts = False

                store.mas_utils.writelog("[WARNING]: Xlib failed to be imported, disabling notifications.\n")

        else:
            can_show_notifs = False
            can_do_windowreacts = False

            store.mas_utils.writelog("[WARNING]: Cannot detect current session type, disabling notifications.\n")

    else:
        can_do_windowreacts = False


    #Now, we start defining OS specific functions which we can swap out
    def _getActiveWindow_Windows(friendly):
        """
        Funtion to get the active window on Windows systems

        IN:
            friendly - Whether or not we want the active window handle in a usable format

        OUT:
            string representing the active window handle

        ASSUMES: OS IS WINDOWS (renpy.windows)
        """
        window_handle = GetWindowText(GetForegroundWindow())
        if friendly:
            return window_handle
        else:
            return window_handle.lower().replace(" ","")

    def _getActiveWindow_Linux(friendly):
        """
        Funtion to get the active window on Linux systems

        IN:
            friendly - Whether or not we want the active window handle in a usable format

        OUT:
            string representing the active window handle

        ASSUMES: OS IS LINUX (renpy.linux)
        """
        NET_WM_NAME = __display.intern_atom("_NET_WM_NAME")
        NET_ACTIVE_WINDOW = __display.intern_atom("_NET_ACTIVE_WINDOW")

        # Perform nullchecks on property getters, just in case.
        active_winid_prop = __root.get_full_property(NET_ACTIVE_WINDOW, 0)

        if active_winid_prop is None:
            return ""

        active_winid = active_winid_prop.value[0]

        active_winobj = display.create_resource_object("window", active_winid)
        try:
            # Subsequent method calls might raise BadWindow exception if active_winid refers to nonexistent window.
            active_winname_prop = active_winobj.get_full_property(NET_WM_NAME, 0)

            if active_winname_prop is not None:
                active_winname = unicode(active_winname_prop.value)
                return (
                    active_winname.replace("\n", "")
                    if friendly
                    else active_winname.lower().replace(" ", "").replace("\n", "")
                )

            else:
                return ""

        except BadWindow:
            return ""

    def _getActiveWindow_OSX(friendly):
        """
        Gets the active window on macOS

        IN:
            friendly - Whether or not we want the output in a usable state

        NOTE: This currently just returns an empty string, this is because we do not have active window detection
        for MacOS
        """
        return ""

    def _tryShowNotification_Windows(title, body):
        """
        Tries to push a notification to the notification center on Windows.
        If it can't it should fail silently to the user.

        IN:
            title - notification title
            body - notification body

        OUT:
            bool. True if the notification was successfully sent, False otherwise
        """
        # The Windows way, notif_success is adjusted if need be
        notif_success = __tip.showWindow(renpy.substitute(title), renpy.substitute(renpy.random.choice(body)))

        #We need the IDs of the notifs to delete them from the tray
        destroy_list.append(__tip.hwnd)
        return notif_success

    def _tryShowNotification_Linux(title, body):
        """
        Tries to push a notification to the notification center on Linux.
        If it can't it should fail silently to the user.

        IN:
            title - notification title
            body - notification body

        OUT:
            bool - True, representing the notification's success
        """
        # Single quotes have to be escaped.
        # Since single quoting in POSIX shell doesn't allow escaping,
        # we have to close the quotation, insert a literal single quote and reopen the quotation.
        body  = body.replace("'", "'\\''")
        title = title.replace("'", "'\\''") # better safe than sorry
        os.system("notify-send '{0}' '{1}' -a 'Monika' -u low".format(title,body))
        return True

    def _tryShowNotification_OSX(title, body):
        """
        Tries to push a notification to the notification center on macOS.
        If it can't it should fail silently to the user.

        IN:
            title - notification title
            body - notification body

        OUT:
            bool - True, representing the notification's success
        """
        os.system('osascript -e \'display notification "{0}" with title "{1}"\''.format(body,title))
        return True

    def _getAbsoluteMousePos_Windows():
        """
        Returns an (x, y) co-ord tuple for the mouse position

        OUT:
            tuple representing the absolute position of the mouse
        """
        if store.mas_windowreacts.can_do_windowreacts:
            #Try except here because we may not have permissions to do so
            try:
                cur_pos = store.win32gui.GetCursorPos()
            except:
                cur_pos = DEF_MOUSE_POS_RETURN

        else:
            cur_pos = DEF_MOUSE_POS_RETURN

        return cur_pos

    def getMASWindowHWND():
        """
        Gets the hWnd of the MAS window

        NOTE: Windows ONLY

        OUT:
            int - represents the hWnd of the MAS window
        """
        def checkMASWindow(hwnd, lParam):
            """
            Internal function to identify the MAS window. Raises an exception when found to allow the main func to return
            """
            if renpy.config.window_title in store.win32gui.GetWindowText(hwnd):
                raise Exception(hwnd)

        try:
            store.win32gui.EnumWindows(checkMASWindow, None)
        except Exception as e:
            return e.message

    def getMASWindowPosWin():
        """
        Gets the window position for MAS as a tuple of (left, top, right, bottom)

        OUT:
            tuple representing window geometry or None if the window's hWnd could not be found
        """
        hwnd = getMASWindowHWND()

        if hwnd is None:
            return None

        return store.win32gui.GetWindowRect(hwnd)

    #Finally, we set vars accordingly to use the appropriate functions without needing to run constant runtime checks
    if renpy.windows:
        __window_get = _getActiveWindow_Windows
    else:
        __window_get = _getActiveWindow_Linux if renpy.linux else: _getActiveWindow_Mac

    if renpy.windows:
        __tryShowNotif = _tryShowNotification_Windows
    else:
        __window_get = _tryShowNotification_Linux if renpy.linux else: _tryShowNotification_OSX

init python:
    #List of notif quips (used for topic alerts)
    #Windows/Linux
    mas_win_notif_quips = [
        "[player], I want to talk to you about something.",
        "Are you there, [player]?",
        "Can you come here for a second?",
        "[player], do you have a second?",
        "I have something to tell you, [player]!",
        "Do you have a minute, [player]?",
        "I've got something to talk about, [player]!",
    ]

    #OSX, since no active window detection
    mas_other_notif_quips = [
        "I've got something to talk about, [player]!",
        "I have something to tell you, [player]!",
        "Hey [player], I want to tell you something.",
        "Do you have a minute, [player]?",
    ]

    #List of hwnd IDs to destroy
    destroy_list = list()

    #START: Utility methods
    def mas_canCheckActiveWindow():
        """
        Checks if we can check the active window (simplifies conditionals)
        """
        return (
            store.mas_windowreacts.can_do_windowreacts
            and (persistent._mas_windowreacts_windowreacts_enabled or persistent._mas_enable_notifications)
        )

    def mas_getActiveWindow(friendly=False):
        """
        Gets the active window name
        IN:
            friendly: whether or not the active window name is returned in a state usable by the user
                (Default: False)

        OUT:
            The active window handle if found. If it is not possible to get, we return an empty string

        NOTE: THIS SHOULD NEVER RETURN NONE
        """
        if mas_windowreacts.can_show_notifs and mas_canCheckActiveWindow():
            return store.mas_windowreacts.__window_get(friendly)
        return ""

    def mas_display_notif(title, body, group=None, skip_checks=False):
        """
        Notification creation method

        IN:
            title - Notification heading text
            body - A list of items which would go in the notif body (one is picked at random)
            group - Notification group (for checking if we have this enabled)
                (Default: None)
            skip_checks - Whether or not we skips checks
                (Default: False)
        OUT:
            bool indicating status (notif shown or not (by check))

        NOTE:
            We only show notifications if:
                1. We are able to show notifs
                2. MAS isn't the active window
                3. User allows them
                4. And if the notification group is enabled
                OR if we skip checks. BUT this should only be used for introductory or testing purposes.
        """

        #First we want to create this location in the dict, but don't add an extra location if we're skipping checks
        if persistent._mas_windowreacts_notif_filters.get(group) is None and not skip_checks:
            persistent._mas_windowreacts_notif_filters[group] = False

        if (
            skip_checks
            or (
                mas_windowreacts.can_show_notifs
                and ((renpy.windows and not mas_isFocused()) or not renpy.windows)
                and mas_notifsEnabledForGroup(group)
            )
        ):
            #Now we make the notif
            notif_success = mas_windowreacts.__tryShowNotif(
                renpy.substitute(title),
                renpy.substitute(renpy.random.choice(body))
            )

            #Play the notif sound if we have that enabled and notif was successful
            if persistent._mas_notification_sounds and notif_success:
                renpy.sound.play("mod_assets/sounds/effects/notif.wav")

            #Now we return true if notif was successful, false otherwise
            return notif_success
        return False

    def mas_isFocused():
        """
        Checks if MAS is the focused window
        """
        #TODO: Mac vers (if possible)
        return store.mas_windowreacts.can_show_notifs and mas_getActiveWindow(True) == config.window_title

    def mas_isInActiveWindow(keywords, non_inclusive=False):
        """
        Checks if ALL keywords are in the active window name
        IN:
            keywords:
                List of keywords to check for

            non_inclusive:
                Whether or the not the list is checked non-inclusively
                (Default: False)
        """

        #Don't do work if we don't have to
        if not store.mas_windowreacts.can_show_notifs:
            return False

        #Otherwise, let's get the active window
        active_window = mas_getActiveWindow()

        if non_inclusive:
            return len([s for s in keywords if s.lower() in active_window]) > 0
        else:
            return len([s for s in keywords if s.lower() not in active_window]) == 0

    def mas_clearNotifs():
        """
        Clears all tray icons (also action center on win10)
        """
        if renpy.windows and store.mas_windowreacts.can_show_notifs:
            for index in range(len(destroy_list)-1,-1,-1):
                win32gui.DestroyWindow(destroy_list[index])
                destroy_list.pop(index)

    def mas_checkForWindowReacts():
        """
        Runs through events in the windowreact_db to see if we have a reaction, and if so, queue it
        """
        #Do not check anything if we're not supposed to
        if not persistent._mas_windowreacts_windowreacts_enabled or not store.mas_windowreacts.can_show_notifs:
            return

        for ev_label, ev in mas_windowreacts.windowreact_db.iteritems():
            if (
                Event._filterEvent(ev, unlocked=True, aff=store.mas_curr_affection)
                and mas_isInActiveWindow(ev.category, "non inclusive" in ev.rules)
                and ((not store.mas_globals.in_idle_mode) or (store.mas_globals.in_idle_mode and ev.show_in_idle))
                and mas_notifsEnabledForGroup(ev.rules.get("notif-group"))
            ):
                #If we have a conditional, eval it and queue if true
                if ev.conditional and eval(ev.conditional):
                    queueEvent(ev_label)
                    ev.unlocked=False

                #Otherwise we just queue
                elif not ev.conditional:
                    queueEvent(ev_label)
                    ev.unlocked=False

                #Add the blacklist
                if "no_unlock" in ev.rules:
                    mas_addBlacklistReact(ev_label)

    def mas_resetWindowReacts(excluded=persistent._mas_windowreacts_no_unlock_list):
        """
        Runs through events in the windowreact_db to unlock them
        IN:
            List of ev_labels to exclude from being unlocked
        """
        for ev_label, ev in mas_windowreacts.windowreact_db.iteritems():
            if ev_label not in excluded:
                ev.unlocked=True

    def mas_updateFilterDict():
        """
        Updates the filter dict with the groups in the groups list for the settings menu
        """
        for group in store.mas_windowreacts._groups_list:
            if persistent._mas_windowreacts_notif_filters.get(group) is None:
                persistent._mas_windowreacts_notif_filters[group] = False

    def mas_addBlacklistReact(ev_label):
        """
        Adds the given ev_label to the no unlock list
        IN:
            ev_label: eventlabel to add to the no unlock list
        """
        if renpy.has_label(ev_label) and ev_label not in persistent._mas_windowreacts_no_unlock_list:
            persistent._mas_windowreacts_no_unlock_list.append(ev_label)

    def mas_removeBlacklistReact(ev_label):
        """
        Removes the given ev_label to the no unlock list if exists
        IN:
            ev_label: eventlabel to remove from the no unlock list
        """
        if renpy.has_label(ev_label) and ev_label in persistent._mas_windowreacts_no_unlock_list:
            persistent._mas_windowreacts_no_unlock_list.remove(ev_label)

    def mas_notifsEnabledForGroup(group):
        """
        Checks if notifications are enabled, and if enabled for the specified group
        IN:
            group: notification group to check
        """
        return persistent._mas_enable_notifications and persistent._mas_windowreacts_notif_filters.get(group,False)

    def mas_unlockFailedWRS(ev_label=None):
        """
        Unlocks a wrs again provided that it showed, but failed to show (failed checks in the notif label)
        NOTE: This should only be used for wrs that are only a notification
        IN:
            ev_label: eventlabel of the wrs
        """
        if (
            ev_label
            and renpy.has_label(ev_label)
            and ev_label not in persistent._mas_windowreacts_no_unlock_list
        ):
            mas_unlockEVL(ev_label,"WRS")

    def mas_prepForReload():
        """
        Handles clearing wrs notifs and unregistering the wndclass to allow 'reload' to work properly

        ASSUMES: renpy.windows
        """
        store.mas_clearNotifs()
        win32gui.UnregisterClass(__tip.classAtom, __tip.hinst)
