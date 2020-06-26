#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2015 Murat Guven <muratg@online.de>
# This plugin helps you managing themes for the Windows version of
# ZimWiki from Jaap Karssenberg
# V0.73 for Zim >=0.61

# Change Log
# V0.73 Check if Zim Wiki was installed into Program Files folder (no working due to UAC)
# V0.72 Added stop button and function. Further restructured code. Improved error messages
# V0.71 Minor change in Progress bar status texts
# V0.70	Added disable buttons when importing and restructured code, renamed plugin
# V0.68	Re-design of gui moving away from options to buttons which makes the gui easier to use
# V0.67 Added double click for selecting and rename themes
# V0.66 Improved message dialog for deleting themes
# V0.65 Added progress bar
# V0.64 Adding multi select for deletion
# V0.63 Added pixbuf to list elements in theme list to make the themes entries more visible
# V0.62	Added change of button text on option selected + hide / unhide themes list to make the gui easier to comprehend
# V0.60 First release

import gtk
import shutil
import sys
import os
import zipfile
import tarfile
import string
import gobject
import threading
import random, time
import multiprocessing
import threading

from zim.plugins import PluginClass, WindowExtension, extends
from zim.actions import action
from zim.config import ConfigManager
import zim.datetimetz as datetime
from zim.config import StringAllowEmpty
from zim.config import ZIM_DATA_DIR
from zim.fs import *
from zim.gui import widgets
from zim.applications import Application, ApplicationError

ZIM_HOME = string.rstrip(str(ZIM_DATA_DIR), 'data')
GTK_FILE = "\\gtk-2.0\\gtkrc"
THEME_PATH = ZIM_HOME + "\\share\\themes\\"
STOP = "Stopped..."
ERROR = "Error..."
FINISHED = 'Finished...'

zim_cmd = ('zim')
zim_cmd_portable = ('ZimDesktopWikiPortable')

gtk.threads_init()

class ThemeManagerPlugin(PluginClass):
	plugin_info = {
		'name': _('Theme Manager'),  # T: plugin name
		'description': _('''\
This plugin helps you managing themes for the Windows version of Zim.
Zim must not be installed into Program Files folder as files need to
changed within the Zim directories.

(V0.73)
'''),  # T: plugin description
		'author': "Murat Güven",
		'help': 'Plugins:Theme Manager',
	}

	plugin_preferences = (
	# T: label for plugin preferences dialog
	# T: plugin preference
	)

	@classmethod
	def check_dependencies(klass):
		os_name = os.name
		if os_name == "nt":
			os_windows = True
			if "Program Files" in ZIM_HOME:
				program_files = False
			else:
				program_files = True
		#has_zim_exe = Application(zim_cmd).tryexec()
		#has_zim_exe_portable = Application(zim_cmd_portable).tryexec()

		zim_windows = False
		if os.path.isfile(ZIM_HOME + "zim.exe") or os.path.isfile(ZIM_HOME + "ZimDesktopWikiPortable.exe"):
			zim_windows = True

		

		return (os_windows and zim_windows and program_files), \
				[('Windows', os_windows, True), ('Zim Wiki for Windows', zim_windows, True), ('Zim Wiki installed outside Program Files', program_files, True)]

@extends('MainWindow')
class ThemeManagerMainWindowExtension(WindowExtension):
	uimanager_xml = '''
	<ui>
	<menubar name='menubar'>
		<menu action='tools_menu'>
			<placeholder name='plugin_items'>
				<menuitem action='theme_manager'/>
			</placeholder>
		</menu>
	</menubar>
	</ui>
	'''

	@action(_('_Theme Manager'))  # T: menu item
	def theme_manager(self):	
		# as this Plugin is only useful for the Windows version of Zim...
		if os.name != "nt":
			self.show_message("Red", "This plugin can be used for the Windows Version of Zim only!")
		self.button = ""
		self.window = gtk.Window()
		#self.window = widgets.Window()
		self.mainbox = gtk.VBox()

		self.progress_bar = gtk.ProgressBar()
		self.label_headline = gtk.Label("<big><b>ZimWiki - Theme Manager </b></big>")

		self.button_select_theme = gtk.Button("Set")				
		self.button_delete_theme = gtk.Button("Delete")			
		self.button_rename_theme = gtk.Button("Rename")			
		self.button_import_file = gtk.Button("Import file")			
		self.button_import_dir = gtk.Button("Import dir")			
		self.button_stop = gtk.Button("Stop")	
		self.button_stop.set_sensitive(False)											# Stop button shall be selectable only when something is happening

		self.store = gtk.ListStore(gtk.gdk.Pixbuf, str, str)		
		self.treeview = gtk.TreeView(model=self.store)
		self.treeview.connect("row-activated", self.select_theme_double_clicked)		# If double clicked on theme name in tree
		
		self.frame_theme_name = gtk.Frame()
		self.frame_theme_name.set_size_request(300,60)
		self.frame_message_field = gtk.Frame()
		self.frame_message_field.set_size_request(300,160)

		self.message_field = gtk.VBox()
		self.message_box = gtk.Label()
		self.message_box.set_use_markup(True)
		self.message_box.set_size_request(300, 90)
		self.hbox1_buttons = gtk.HBox(True, 10)
		self.hbox2_buttons = gtk.HBox(True, 10)
		self.scrolled_window = gtk.ScrolledWindow()

		# do the main plugin window	
		self.window.set_title("ZimWiki - Theme Manager")
		self.window.set_border_width(5)
		self.window.set_size_request(320, 600)
		self.window.set_position(gtk.WIN_POS_CENTER)
		#self.window.connect( "destroy", self.destroy)

		self.window.add(self.mainbox)

		# Add the plugin headline
		self.label_headline.set_use_markup(True)
		self.mainbox.pack_start(self.label_headline, expand=False, padding=5)

		# add frame for current theme name
		self.frame_theme_name.set_label("Current theme")
		self.frame_theme_name.set_shadow_type(gtk.SHADOW_ETCHED_IN)
		self.mainbox.pack_start(self.frame_theme_name, expand=False, padding=15)

		# tries to open the gtkrc file in order to display the current theme set. If not Windows version (python script on Windows is also not theme-able)
		# or not found, then show errors and close window
		gtkrc_file, line_no, self.gtkrc_theme_name = self.get_gtkrc(ZIM_HOME)
		self.theme_name=[]						# make the theme_name a list as several entries can be selected for deletion
			
		if not self.gtkrc_theme_name:			# If there is no theme name, it means, the gtkrc file was not found --> then destroy the window after the warning message
			self.window.destroy()
		else:
			# so we have opened the gtkrc file successfully
			# show the current theme name in main window
			self.theme_name.append(self.gtkrc_theme_name.lstrip("gtk-theme-name = "))	# remove this text
			self.theme_name[0] = self.theme_name[0].strip("\"")							# remove apostrophes
			self.theme_label = gtk.Label('<b>'+ self.theme_name[0] + '</b>')
			self.theme_label.set_use_markup(True)
			self.current_theme = self.theme_name[0]
			self.frame_theme_name.add(self.theme_label)
			self.theme_name=[]								# clear again in order to prevent deletion dialog of current_theme if delete is clicked and no theme is selected.

		self.scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)	

		# show available themes
		self.show_themes(self.mainbox)
		
		# Buttons
		self.mainbox.pack_start(self.hbox1_buttons, expand=False, padding=5)
		self.mainbox.pack_start(self.hbox2_buttons, expand=False, padding=5)
	
		self.hbox1_buttons.add(self.button_select_theme)
		self.hbox1_buttons.add(self.button_rename_theme)
		self.hbox1_buttons.add(self.button_delete_theme)
		self.hbox2_buttons.add(self.button_import_file)
		self.hbox2_buttons.add(self.button_import_dir)
		self.hbox2_buttons.add(self.button_stop)
		
		self.button_select_theme.connect("clicked", self.button_clicked, "select")
		self.button_delete_theme.connect("clicked", self.button_clicked, "delete")
		self.button_rename_theme.connect("clicked", self.button_clicked, "rename")
		self.button_import_file.connect("clicked", self.button_clicked, "file")	
		self.button_import_dir.connect("clicked", self.button_clicked, "dir")
		
		# Status field
		# set a frame for the status field
		self.frame_message_field.set_label("Status")
		self.frame_message_field.set_shadow_type(gtk.SHADOW_ETCHED_IN)
		self.mainbox.pack_start(self.frame_message_field, expand=False, padding=5)

		self.frame_message_field.add(self.message_field)

		# set a box for status messages
		self.message_field.pack_start(self.message_box, expand=False, padding=10)

		# progress bar for importing theme files which need time to extract
		self.message_field.pack_start(self.progress_bar, expand=False, padding=5)

		self.mainbox.show_all()
		self.window.show_all()

		self.progress_bar.hide()														# don't show progress_bar in the main screen in the beginning
		self.window.connect('key_press_event', self.get_key_event_main)					# to grab F2 for rename
		
		# little guide
		self.show_message("Black", "You can also double click to set a theme.",
							"Invalid themes can't be set.",
							"Use also F2 for rename. Also type to select theme.",
							"Import theme file in tar.gz format.",
							"Import extracted theme file as directory.") 

	def button_clicked(self, widget, data=None):
		self.set_button_sensitive(state=False)
		self.button = data
		if self.button == "select":
			self.reset_status()
			if not self.theme_name:
				theme_name_select = False											# just using self.theme_name[0], as parameter for set_selected_theme brings index error if empty
			else:
				theme_name_select = self.theme_name[0]
			self.set_selected_theme(theme_name_select, pbarstatus="Setting finished...")			# Just pass the 1. element of theme_names as only one selection is possible to set as theme
		if self.button == "rename":
			self.reset_status()
			self.rename_theme(self.theme_name)				
		if self.button == "delete":
			self.reset_status()
			self.delete_theme(None, self.theme_name)								# Pass all theme_names, as multiple themes can be selected.				
		if self.button == "file":
			self.reset_status()
			self.choose_theme_file(None, self.mainbox)
		if self.button == "dir":
			self.reset_status()
			self.choose_theme_dir(None, self.mainbox)

	def set_button_sensitive(self, state):
		self.button_select_theme.set_sensitive(state)
		self.button_delete_theme.set_sensitive(state)
		self.button_rename_theme.set_sensitive(state)
		self.button_import_file.set_sensitive(state)
		self.button_import_dir.set_sensitive(state)
		self.button_stop.set_sensitive(not state)

########################  Create GUI END ###################################################

# START ################  Option import theme directory ####################################
	def choose_theme_dir(self, widget, mainbox):
		# Open FileDialog, but only directories are selectable
		dir_dialog = gtk.FileChooserDialog( title="Select a theme directory",
									parent=self.window,
									action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
									buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OK,gtk.RESPONSE_OK)
									)
		dir_dialog.connect("response", self.dir_dialog_response)
		dir_dialog.show()
		
	def dir_dialog_response(self, widget, response_id):
		# If user selected a directory and clicked OK
		if response_id == gtk.RESPONSE_OK:
			fullname = widget.get_current_folder()
			theme_path, theme_name = os.path.split(fullname)
			dest = (ZIM_HOME + "\\share\\themes\\" + theme_name +"\\")			# This is the directory for themes in the Windows version of ZIM
			widget.destroy()													# close the dir dialog to see the progressbar
			self.import_theme_dir(fullname, dest, theme_name)					# If import was successful then select theme
		self.renew_store()
		widget.destroy()														# destroy FileChooserDialog

	def import_theme_dir(self, fullname, dest, theme_name):
		self.progress_bar.show()
		copy = Interface(fullname, dest, None, self.progress_bar, self.button, self.button_stop)
		copy.main()
		status = self.progress_bar.get_text()				# use for getting status
		if status == FINISHED:
			self.set_selected_theme(theme_name, pbarstatus="Import is finished...")
		else:
			self.show_message("red","Error while importing theme directory!", "The theme seems to exist already.",
								"Available themes refreshed.")


# END ##################  Option import theme directory ####################################


# START ################  Option import theme file #########################################
	def choose_theme_file(self, widget, mainbox):
		file_dialog = gtk.FileChooserDialog(title="Select a theme file",
									parent=self.window,
									action=gtk.FILE_CHOOSER_ACTION_OPEN,
									buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OK,gtk.RESPONSE_OK)
									)

		file_dialog.connect("response", self.file_dialog_response)
		file_dialog.show()

	def file_dialog_response(self, widget, response_id):
		# If user selected a directory and clicked OK
		theme_untar_name = []											# the directory name of the theme could be different from the name of the tar file
		if response_id == gtk.RESPONSE_OK:								# When OK was clicked
			self.fullname = widget.get_filename()						# get the selected file name
			theme_path, theme_name = os.path.split(self.fullname)
			self.destdir = (ZIM_HOME + "share\\themes")					# This is the directory for themes in the Windows version of ZIM
			widget.destroy()											# to see the progressbar
			self.import_theme_file(self.fullname, self.destdir)			# untar and if it was succesfully untared, then the untar name was returned, else False returned
			self.renew_store()											# clear up the list of available themes and populate again with all directories in theme folder which contain a  gtk-2.0/gtkrc file
		self.renew_store()
		widget.destroy()												# destroy FileChooserDialog

	def import_theme_file(self, fname, destdir):
		if tarfile.is_tarfile(fname):									# check if this is really a tar file
			tar = tarfile.open(fname)									# TODO: could be optimized and FINISHED in the worker thread, but communication needs to be re-FINISHED
			tar_names = tar.getnames()									# get the content of the tar file in order to get the directory (theme) name
			tar.close()

			self.progress_bar.show()									# show progress_bar only when something is FINISHED
			import_file = Interface(fname, destdir, None, self.progress_bar, self.button, self.button_stop)
			import_file.main()

			status = self.progress_bar.get_text()			
			if status == STOP:
				self.show_message ("Red", "Import stopped!", "Manually delete already imported themes","which are invalid.")
				return
			
			theme_name = tar_names[0]									# get the first entry in the tar file
			index = theme_name.find("/")								# trying to get a clean name of the theme directory.
			if index != -1:												# if slash / is found
				theme_name = theme_name[0:index]	# cut off everything after the slash /		
			if os.path.isdir(destdir + "\\" + theme_name):			# If this is a proper theme file, then first entry within the tar content is the directory name
				if not os.path.isfile(destdir + "\\" + theme_name + GTK_FILE):	# and if there is no gtkrc file, then this is not a proper theme folder
					self.show_message("Red", "Theme file " +"<b>" + theme_name + "</b>","extracted but no theme found in destination directory.", "", "<u>Possible reasons:</u>", "Theme file is not a theme file or","several themes (dirs) in one file!") # show the success
					self.set_progress_bar("Error...", 0.0)
					return
			if theme_name:
				self.set_selected_theme(theme_name, pbarstatus="Import is finished...")		# set the theme in gtkrc config file
		else:
			self.set_progress_bar("Error...", 0.0)
			self.show_message("Red", "File seems not to be a tar file.","Please uncompress yourself and import the theme directory.") # show the success
			return

# END ##################  Option import theme file #########################################

# START ################  Option delete theme  #############################################
	def delete_theme(self, widget, theme_name):	
		if not theme_name:
			self.show_message("Red", "Please select a theme!")
			self.renew_store()
			return False
		theme_names = ""
		self.progress_bar.show()			# show progress_bar only when something is FINISHED
		for theme in theme_name:	
			theme_names = theme_names + "\n" + theme			# Add all theme names selected for deletion from a list into a string
		self.question_dialog(text="Delete theme(s)?\n" + theme_names)
		return

	def question_dialog_response(self, widget, message_dialog_response):
		if message_dialog_response == 1:					# not to respond if ESC key is pressed
			widget.destroy()								# first destroy the dialog then start deleting...
			self.del_theme(self.theme_name)
		widget.destroy()
		self.renew_store()

	def del_theme(self, theme_names):
		del_themes = Interface(None, None, theme_names, self.progress_bar, self.button, self.button_stop)
		del_themes.main()

		status = self.progress_bar.get_text()
		if status == FINISHED:
			self.show_message("Black", "Theme(s) successfully deleted!")
		elif status == STOP:
			self.show_message("Red", "Deletion stopped!")
		elif status == "Directory delete error!":
			self.show_message("Red", "Error while deleting!", "The selected theme seems not to exist any more.", "Available themes refreshed...")
		
	
# End ##################  Option delete theme  #############################################

# START ################  Option set theme  ################################################
	def select_theme_double_clicked(self, treeview, path, view_column):
		self.select_theme(None)
		self.set_selected_theme(self.theme_name[0], pbarstatus="Setting finished...")

	def select_theme(self, widget):
		(model, pathlist) = self.tree_selection.get_selected_rows()
		self.theme_name = []						# need to empty theme_name list in order to append only selected themes from treestore into this list, otherwise I get old selected and newly selected themes
		for path in pathlist:
			tree_iter = model.get_iter(path)
			self.theme_name.append(model.get_value(tree_iter, 1))
		return
# End ##################  Option set theme  ################################################


# START ################  Rename theme  ####################################################
	def rename_theme(self, theme_name):
		if not theme_name:
			theme_name_rename = self.current_theme
		else:
			theme_name_rename = self.theme_name[0]
		self.rename_dialog(theme_name_rename)

	def rename_dialog(self, theme_name):
		rename_dialog = gtk.Dialog(None, parent=self.window, flags=gtk.DIALOG_DESTROY_WITH_PARENT, buttons=("OK", True, "Cancel", False))
		entry = gtk.Entry()
		entry.set_text(theme_name)
		rename_dialog.vbox.pack_start(entry)
		rename_dialog.connect("response", self.rename_dialog_response, theme_name, entry, rename_dialog)
		entry.connect('key_press_event', self.get_key_event, entry, rename_dialog, theme_name)
		rename_dialog.show_all()

	def rename_dialog_response(self, widget, message_dialog_response, theme_name, entry, dialog):
		if message_dialog_response:
			theme_name_old = theme_name
			theme_name_new = entry.get_text()

			if theme_name_old == theme_name_new:				# no changes
				self.renew_store()
				dialog.destroy()
				return			
			theme_name_old_path = THEME_PATH + theme_name_old
			theme_name_new_path = THEME_PATH + theme_name_new
			try:
				os.rename(theme_name_old_path, theme_name_new_path)
				if theme_name_old == self.current_theme:										# If rename pushed without selecting a theme, then current_theme can be renamed.
					self.set_selected_theme(theme_name_new, pbarstatus="Setting finished...")						# then update current_theme_name
				self.show_message("Black", "Theme renamed!")
				self.set_progress_bar("Rename finished...", 1.0 )
			except EnvironmentError:
				widget.destroy()
				self.show_message("Red", "Error while renaming theme!",
									"Selected theme seems not to exist or duplicate names.",
									"Available themes refreshed.")
				self.renew_store()
				return
			self.renew_store()
		self.renew_store()
		widget.destroy()
# End ##################  Rename theme  ####################################################

# START ################  General functions ################################################
	def show_store(self, store):
		renderer_pb = gtk.CellRendererPixbuf()        
		column = gtk.TreeViewColumn('Available themes')
		column.pack_start(renderer_pb, expand=False)
		column.add_attribute(renderer_pb, 'pixbuf', 0)
		
		renderer_txt = gtk.CellRendererText()        
		column.pack_start(renderer_txt, expand=True)
		column.add_attribute(renderer_txt, 'text', 1)
		
		renderer_valid = gtk.CellRendererText()
		column.pack_start(renderer_valid, expand=True)
		column.add_attribute(renderer_valid, 'text', 2)

		self.treeview.append_column(column)

		# Use ScrolledWindow to make the TreeView scrollable
		# Only allow vertical scrollbar
		self.scrolled_window.add(self.treeview)
		self.tree_selection = self.treeview.get_selection()
		self.tree_selection.set_mode(gtk.SELECTION_MULTIPLE)
		self.tree_selection.connect("changed", self.select_theme)

		self.mainbox.add(self.scrolled_window)
		self.mainbox.show_all()

	def show_themes(self, mainbox):
		#store = gtk.ListStore(str)
		self.populate_store(self.store)
		self.show_store(self.store)
		return

	def renew_store(self):
		self.store.clear()
		self.populate_store(self.store)
		self.theme_name = []
		self.set_button_sensitive(state=True)

	def populate_store(self, store):
		for dirname in os.listdir(THEME_PATH):
			if os.path.isfile(THEME_PATH + dirname + GTK_FILE):			# only show gtk themes
				if dirname == self.current_theme:
					continue
				store.append([self.get_icon_pixbuf(), dirname, 'valid'])
			else:
				store.append([self.get_icon_pixbuf(), dirname, 'invalid'])
		return

	def get_icon_pixbuf(self):
		return self.treeview.render_icon(gtk.STOCK_CONVERT,
                                size=gtk.ICON_SIZE_MENU,
                                detail=None)

	def set_selected_theme(self, theme_name, pbarstatus=None):
		if not theme_name:
			self.show_message("Red", "Please select a theme!") # Select theme clicked without selecting a theme from treestore
			#self.set_progress_bar("Error...", 0.0)
			self.renew_store()
			return False
		if self.change_gtkrc(theme_name):
			self.show_message('black', 'Theme successfully changed to:', "", theme_name, "", 'Please restart Zim to take effect the new theme.') # show the success
			self.renew_store()
			self.set_progress_bar(pbarstatus, 1.0)

	def set_progress_bar(self, status, fraction):
		self.progress_bar.show()
		self.progress_bar.set_text(status)
		self.progress_bar.set_fraction(fraction)

	def update_theme_label(self, label, theme_name):
		# to update the theme name in main window
		label.set_label('<b>' + theme_name + '</b>')
		self.current_theme = theme_name
		return
		
	def change_gtkrc(self, theme_name):
		gtkrc_file, line_no, theme_old_name = self.get_gtkrc(ZIM_HOME)
		if not os.path.isfile(ZIM_HOME + "\\share\\themes\\" + theme_name + GTK_FILE):
			self.show_message("Red", "Theme could not be set!", "", "<u>Possible reasons</u>:","Theme is not valid or multiple themes imported.")
			self.set_progress_bar("Error...", 0.0)
			return False
		theme = "gtk-theme-name = " + "\"" + theme_name + "\"" + "\n"
		try:
			self.replace_line(gtkrc_file,line_no,theme)
			self.update_theme_label(self.theme_label, theme_name)					# Update theme name in Window
		except EnvironmentError:
			self.show_message("Red", "Error while changing theme! Configuration file could not be updated!")
			return False
		return True

	def get_gtkrc(self, ZIM_HOME):
		# tries to open the gtkrc file. If not Windows version or not found, then show error
		gtkrc_PATH = ZIM_HOME + "\\etc"
		gtkrc_file = gtkrc_PATH + GTK_FILE
		theme_name = ""
		try:
			gtkrc_in = open(gtkrc_file, "r")
			line_no = 0
			for line in gtkrc_in.readlines():
				line = line.strip()
				if line.startswith("gtk-theme-name"):
					theme_name = line					# found the theme name
					break
				else:
					line_no += 1
					continue
		except EnvironmentError:
			self.show_message("Red", "gtkrc file does not exist!","Is this the Windows version of Zim?")
			gtkrc_file=False
			line_no=False
			theme_name=""

		if theme_name == "":							# scanned through all lines in gtkrc file and found nothing...:( Should not be the case, but who knows ;)
			theme_name = "No theme name found!"

		return gtkrc_file, line_no, theme_name

	def replace_line(self, file_name, line_num, new_theme):
		lines = open(file_name, 'r').readlines()
		if line_num > len(lines)-1:			# -1 as first line starts with Index 0
			lines.append("\n" + new_theme)	# with line feed just in case there is none at the end of the existing line
		else:
			lines[line_num] = new_theme		# so add the new theme name at the position of the old theme name
		out = open(file_name, 'w')
		out.writelines(lines)
		out.close()
		
	def message_dialog_response(self, widget, response_id, exit):
		widget.destroy()
		self.reset_status()
		if exit:				# I want to exit the plugin, if the operating system is not Windows, otherwise I show some errors / warnings and continue.
			sys.exit()

	def show_message(self, *params):
		colour = params[0]
		message = ""
		for param in params:
			if param == colour:
				continue
			else:
				prefix = '<span foreground=' + "\'" + colour + "\'" + '>'
				suffix = '</span>\n'
				message = message + prefix + param + suffix
		self.message_box.set_label(message)

	def question_dialog(self, text):
		qd = gtk.Dialog(None, parent=self.window, flags=gtk.DIALOG_DESTROY_WITH_PARENT, buttons=("OK", True, "Cancel", False))
		label = gtk.Label(text)
		label.set_padding(10,10)
		sc_win = gtk.ScrolledWindow()
		sc_win.set_size_request(100,100)
		sc_win.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)	
		qd.vbox.pack_start(sc_win)
		sc_win.add_with_viewport(label)
		qd.connect("response", self.question_dialog_response)
		qd.show_all()

	def get_key_event_main(self, widget, event):
		if event.keyval == gtk.gdk.keyval_from_name('F2'):
			self.rename_theme(self.theme_name)

	def get_key_event(self, widget, event, entry, dialog, theme_name):
		if event.keyval == gtk.gdk.keyval_from_name('Escape'):
			self.renew_store()
			dialog.destroy()
		if event.keyval == gtk.gdk.keyval_from_name('Return'):
			self.rename_dialog_response(dialog, True, theme_name, entry, dialog)

	def reset_status(self):
		self.progress_bar.set_fraction(0)
		self.progress_bar.set_text("")
		self.progress_bar.hide()						# Hide the progressbar
		self.message_box.set_label("")
# End ##################  General functions ################################################	

# START ################  Classes for updating process bar #################################
class Listener(gobject.GObject):

	__gsignals__ = {
		'updated' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_FLOAT, gobject.TYPE_STRING)),
		'finished' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
		'error' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_FLOAT, gobject.TYPE_STRING)),
		'stop' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
	}

	def __init__(self, queue):
		gobject.GObject.__init__(self)
		self.queue = queue

	def go(self):
		# Listener
		while True:
			# Listen for results on the queue and process them accordingly                            
			data = self.queue.get()
			# Check if finished                                                                       
			if data[1]==FINISHED:
				self.emit('finished')
				return
			# Check if error
			if data[1]==ERROR:
				self.emit('error', data[0], data[1])
				return
			if data[1]=="Directory import error!":
				self.emit('error', data[0], data[1])
				return
			if data[1]=="Directory delete error!":
				self.emit('error', data[0], data[1])
				return
			# Check if stop clicked
			if data[1]==STOP:
				self.emit('stop')
				return
			else:
				self.emit('updated', data[0], data[1])

gobject.type_register(Listener)


class Worker_import_file():

	def __init__(self, queue, fname, destdir):
		self.queue = queue
		self.fname = fname
		self.destdir = destdir

	def go(self):
		# untar in the Worker process
		tar = tarfile.open(self.fname)
		tar.extractall(path=self.destdir, members = self.track_progress(tar))
		tar.close()
		
	def track_progress(self, tar):
		tar_members_n = len(tar.getmembers())
		pbar_step = (float(1))/tar_members_n
		pbar_fraction = 0
		for member in tar.getmembers():
			pbar_fraction += pbar_step
			self.queue.put((pbar_fraction, "Importing..."))
			yield member
		self.queue.put((1.0, FINISHED))


class Worker_import_dir():

	def __init__(self, queue, fullname, dest):
		self.queue = queue
		self.fullname = fullname
		self.destdir = dest
		self.pbar_step = 0

	def go(self):
		# untar in the Worker process
		all_files_no = 0
		for root, dirs, files in os.walk(self.fullname):
			all_files_no += len(files)						# get all files in source directory for proper fraction calculation of progressbar
		self.pbar_step = (float(1))/all_files_no
		self.pbar_fraction = 0
		try:
			shutil.copytree(self.fullname, self.destdir, ignore=self.track_progress)	# do copy, jump to track_progress at each directory which is to be copied
			self.queue.put((1.0, FINISHED))
		except EnvironmentError:
			self.queue.put((0.0, "Directory import error!"))

	def track_progress(self, path, names):
		self.pbar_fraction += self.pbar_step * len(names)
		if self.pbar_fraction > 1:								# if by any chance the calc was not accurate 100%
			self.pbar_fraction = 1
		self.queue.put((self.pbar_fraction, "Importing..."))
		return []											# jump back to copytree by saying: ignore nothing

		
class Worker_del_dir():

	def __init__(self, queue, theme_names):
		self.queue = queue
		self.theme_names = theme_names
		self.pbar_step = 0
		
	def go(self):
		theme_names_n = len(self.theme_names)
		self.pbar_step = (float(1))/theme_names_n
		self.pbar_fraction = 0
		
		for theme in self.theme_names:
			theme_path = (THEME_PATH + theme +"\\")
			if not os.path.isfile(THEME_PATH+theme):
				try:
					self.queue.put((self.pbar_fraction, "Deleting..."))
					shutil.rmtree(theme_path)
					self.pbar_fraction += self.pbar_step
				except EnvironmentError:
					self.queue.put((0.0, "Directory delete error!"))
					return
			else:
				try:
					self.pbar_fraction += self.pbar_step
					self.queue.put((self.pbar_fraction, "Deleting..."))
					os.remove(THEME_PATH + theme)
				except EnvironmentError:
					self.queue.put((0.0, "Directory delete error!"))
					return
		self.queue.put((1.0, FINISHED))
			

class Interface:

	def __init__(self, fname, dest_dir, theme_names, progress_bar, button_clicked, button_stop):
		self.process = None
		self.progress_bar = progress_bar
		self.fname = fname
		self.dest_dir = dest_dir
		self.theme_names = theme_names			# lazy approach to use for del_dir as well
		self.button = button_clicked
		self.button_stop = button_stop

		self.go(widget=None)

	def main(self):
		gtk.main()

	def destroy(self, widget, data=None):
		gtk.main_quit()

	def callbackDisplay(self, obj, fraction, text, data=None):
			self.progress_bar.set_text(text)
			self.progress_bar.set_fraction(fraction)

	def callbackError(self, obj, fraction, text, data=None):
		if self.process==None:
			raise RuntimeError("No worker process started")
		self.progress_bar.set_fraction(0.0)
		self.progress_bar.set_text(text)
		self.process.join()						
		self.process = None
		self.destroy(widget=None)

	def callbackStop(self, obj, data=None):					
		if self.process==None:
			raise RuntimeError("No worker process started")
		self.progress_bar.set_text(STOP)
		self.process.terminate()						# all FINISHED, join worker process
		self.process = None
		self.destroy(widget=None)

	def callbackFinished(self, obj, data=None):
		if self.process==None:
			raise RuntimeError("No worker process started")
		self.progress_bar.set_fraction(1.0)
		self.progress_bar.set_text(FINISHED)
		self.process.join()						# all FINISHED, join worker process
		self.process = None
		self.destroy(widget=None)

	def go(self, widget, data=None):
		if self.process!=None:
			return
		queue = multiprocessing.Queue()									# Create shared Queue

		##### Create worker
		if self.button == "file":
			worker = Worker_import_file(queue, self.fname, self.dest_dir)
		if self.button == "dir":
			worker = Worker_import_dir(queue, self.fname, self.dest_dir)
		if self.button == "delete":
			worker = Worker_del_dir(queue, self.theme_names)	

		listener = Listener(queue)										# Create Listener
		listener.connect("updated",self.callbackDisplay)
		listener.connect('finished',self.callbackFinished)
		listener.connect('error',self.callbackError)
		listener.connect('stop',self.callbackStop)

		self.process = multiprocessing.Process(target=worker.go, args=())	# Start Worker
		self.process.start()

		thread = threading.Thread(target=listener.go, args=())				# Start Listener
		thread.start()

		self.button_stop.connect("clicked", self.stop_worker, queue)		# Check if Stop button is pressed

	def stop_worker(self, widget, queue):
		queue.put((0.0, STOP))

# End ##################  Classes for updating process bar #################################

