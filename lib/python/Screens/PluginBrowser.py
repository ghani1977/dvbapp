from Screen import Screen
from Screens.ParentalControlSetup import ProtectedScreen
from enigma import eConsoleAppContainer, eDVBDB

from Components.ActionMap import ActionMap, NumberActionMap
from Components.config import config, ConfigSubsection, ConfigText
from Components.PluginComponent import plugins
from Components.PluginList import *
from Components.Label import Label
from Components.Language import language
from Components.Harddisk import harddiskmanager
from Components.Sources.StaticText import StaticText
from Components import Ipkg
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Screens.Console import Console
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_CURRENT_SKIN
from Tools.LoadPixmap import LoadPixmap

from time import time
import os

language.addCallback(plugins.reloadPlugins)

config.misc.pluginbrowser = ConfigSubsection()
config.misc.pluginbrowser.plugin_order = ConfigText(default="")

class PluginBrowserSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent = parent)
		self["entry"] = StaticText("")
		self["desc"] = StaticText("")
		self.onShow.append(self.addWatcher)
		self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		self.parent.onChangedEntry.append(self.selectionChanged)
		self.parent.selectionChanged()

	def removeWatcher(self):
		self.parent.onChangedEntry.remove(self.selectionChanged)

	def selectionChanged(self, name, desc):
		self["entry"].text = name
		self["desc"].text = desc


class PluginBrowser(Screen, ProtectedScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		ProtectedScreen.__init__(self)

		self.firsttime = True
		self.sort_mode = False
		self.selected_plugin = None

		self["key_red"] = self["red"] = Label(_("Remove plugins"))
		self["key_green"] = self["green"] = Label(_("Download plugins"))
		self["key_yellow"] = self["yellow"] = Label("")
		self["key_blue"] = self["blue"] = Label("")

		
		self.list = []
		self["list"] = PluginList(self.list)
		
		self["actions"] = ActionMap(["SetupActions", "WizardActions"],
		{
			"ok": self.keyOk,
			"back": self.keyCancel,
			"menu": self.menu,
		})
		self["PluginDownloadActions"] = ActionMap(["ColorActions"],
		{
			"red": self.delete,
			"green": self.download,
			"blue": self.keyBlue,
		})
		self["SoftwareActions"] = ActionMap(["ColorActions"],
		{
			"red": self.keyRed,
			"green": self.keyGreen,
			"yellow": self.keyYellow,
			"blue": self.keyBlue,
		})
		self["MoveActions"] = ActionMap(["WizardActions"],
			{
				"left": self.keyLeft,
				"right": self.keyRight,
				"up": self.keyUp,
				"down": self.keyDown,
			}, -1)
		self["NumberAction"] = NumberActionMap(["NumberActions"],
			{
				"0": self.resetSortOrder,
			}, -1
		)

		self["PluginDownloadActions"].setEnabled(True)
		self["SoftwareActions"].setEnabled(False)
		self.onFirstExecBegin.append(self.checkWarnings)
		self.onShown.append(self.updateList)
		self.onChangedEntry = []
		self["list"].onSelectionChanged.append(self.selectionChanged)
		self.onLayoutFinish.append(self.saveListsize)

	def isProtected(self):
		return config.ParentalControl.setuppinactive.value and (not config.ParentalControl.config_sections.main_menu.value or hasattr(self.session, 'infobar') and self.session.infobar is None) and config.ParentalControl.config_sections.plugin_browser.value

	def menu(self):
		self.close()

	def saveListsize(self):
		listsize = self["list"].instance.size()
		self.listWidth = listsize.width()
		self.listHeight = listsize.height()

	def createSummary(self):
		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["list"].getCurrent()
		if item:
			p = item[0]
			name = p.name
			desc = p.description
			if self.sort_mode:
				if config.usage.plugin_sort_weight.getConfigValue(name.lower(), "hidden"):
					self["key_yellow"].setText(_("show"))
					self["yellow"].setText(_("show"))
				else:
					self["key_yellow"].setText(_("hide"))
					self["yellow"].setText(_("hide"))
		else:
			name = "-"
			desc = ""
			if self.sort_mode:
				self["key_yellow"].setText("")
				self["yellow"].setText("")
		for cb in self.onChangedEntry:
			cb(name, desc)

	def checkWarnings(self):
		if len(plugins.warnings):
			text = _("Some plugins are not available:\n")
			for (pluginname, error) in plugins.warnings:
				text += _("%s (%s)\n") % (pluginname, error)
			plugins.resetWarnings()
			self.session.open(MessageBox, text = text, type = MessageBox.TYPE_WARNING)

	def save(self):
		self.run()

	def run(self):
		plugin = self["list"].l.getCurrentSelection()[0]
		plugin(session=self.session)

	def setDefaultList(self, answer):
		if answer:
			config.misc.pluginbrowser.plugin_order.value = ""
			config.misc.pluginbrowser.plugin_order.save()
			self.updateList()

	def keyLeft(self):
		self.cur_idx = self["list"].getSelectedIndex()
		self["list"].pageUp()
		if self.sort_mode and self.selected_plugin is not None:
			self.moveAction()

	def keyRight(self):
		self.cur_idx = self["list"].getSelectedIndex()
		self["list"].pageDown()
		if self.sort_mode and self.selected_plugin is not None:
			self.moveAction()

	def keyDown(self):
		self.cur_idx = self["list"].getSelectedIndex()
		self["list"].down()
		if self.sort_mode and self.selected_plugin is not None:
			self.moveAction()

	def keyUp(self):
		self.cur_idx = self["list"].getSelectedIndex()
		self["list"].up()
		if self.sort_mode and self.selected_plugin is not None:
			self.moveAction()

	def moveAction(self):
		entry = self.list.pop(self.cur_idx)
		newpos = self["list"].getSelectedIndex()
		self.list.insert(newpos, entry)
		self["list"].l.setList(self.list)

	def keyYellow(self):
		if self.sort_mode:
			plugin = self["list"].l.getCurrentSelection()[0]
			hidden = config.usage.plugin_sort_weight.getConfigValue(plugin.name.lower(), "hidden") or 0
			if hidden:
				config.usage.plugin_sort_weight.removeConfigValue(plugin.name.lower(), "hidden")
				self["key_yellow"].setText(_("hide"))
				self["yellow"].setText(_("hide"))
			else:
				config.usage.plugin_sort_weight.changeConfigValue(plugin.name.lower(), "hidden", 1)
				self["key_yellow"].setText(_("show"))
				self["yellow"].setText(_("show"))

	def keyBlue(self):
		if config.usage.plugins_sort_mode.value == "user":
			self.toggleSortMode()

	def keyRed(self):
		pass

	def keyCancel(self):
		if self.sort_mode:
			self.toggleSortMode()
		self.close()

	def keyGreen(self):
		if config.usage.plugins_sort_mode.value == "user" and self.sort_mode:
			self.keyOk()

	def keyOk(self):
		if self.sort_mode and len(self.list):
			plugin = self["list"].l.getCurrentSelection()[0]
			select = False
			if self.selected_plugin is None:
				select = True
			elif  self.selected_plugin != plugin:
				select = True
			if not select:
				self.selected_plugin = None
			idx = 0
			for x in self.list:
				if plugin == x[0] and select == True:
					self.list.pop(idx)
					self.list.insert(idx, PluginEntryComponentSelected(x[0], self.listWidth))
					self.selected_plugin = plugin
					break
				elif plugin == x[0] and select == False:
					self.list.pop(idx)
					self.list.insert(idx, PluginEntryComponent(x[0], self.listWidth))
					self.selected_plugin = None
					break
				idx += 1
			if self.selected_plugin is not None:
				self["key_green"].setText(_("Move mode off"))
				self["green"].setText(_("Move mode off"))
			else:
				self["key_green"].setText(_("Move mode on"))
				self["green"].setText(_("Move mode on"))
			self["list"].l.setList(self.list)
		elif len(self.list):
			self.save()

	def resetSortOrder(self, key = None):
		config.usage.plugin_sort_weight.value = {}
		config.usage.plugin_sort_weight.save()
		self.updateList()

	def toggleSortMode(self):
		if self.sort_mode:
			self.sort_mode = False
			i = 10
			idx = 0
			for x in self.list:
				config.usage.plugin_sort_weight.changeConfigValue(x[0].name.lower(), "sort", i)
				if self.selected_plugin is not None:
					if x[0] == self.selected_plugin:
						self.list.pop(idx)
						self.list.insert(idx, PluginEntryComponent(x[0], self.listWidth))
						self.selected_plugin = None
				i += 10
				idx += 1
			config.usage.plugin_sort_weight.save()
			self.updateList()
		else:
			self.sort_mode = True
			self.updateList()

	def updateList(self):
		self.pluginlist = plugins.getPlugins(PluginDescriptor.WHERE_PLUGINMENU)
		empty_sort_order = len(config.usage.plugin_sort_weight.value) or False
		self.list = []
		i = 10
		for plugin in self.pluginlist:
			plugin.listweight = config.usage.plugin_sort_weight.getConfigValue(plugin.name.lower(), "sort") or i
			if self.sort_mode or not config.usage.plugin_sort_weight.getConfigValue(plugin.name.lower(), "hidden"):
				self.list.append(PluginEntryComponent(plugin, self.listWidth))
			i += 10
		if config.usage.plugins_sort_mode.value == "a_z" or (not empty_sort_order and config.usage.plugins_sort_mode.value == "user"):
			self.list.sort(key=lambda p_name : p_name[0].name.lower())
		elif config.usage.plugins_sort_mode.value == "user":
			self.list.sort(key=lambda listweight : listweight[0].listweight)
		self["list"].l.setList(self.list)
		if self.sort_mode:
			self["key_blue"].setText(_("Edit mode off"))
			self["blue"].setText(_("Edit mode off"))
			self["key_green"].setText(_("Move mode off"))
			self["green"].setText(_("Move mode off"))
			self["key_red"].setText("")
			self["red"].setText("")
			self["SoftwareActions"].setEnabled(True)
			self["PluginDownloadActions"].setEnabled(False)
			if self.selected_plugin:
				self["key_green"].setText(_("Move mode off"))
				self["green"].setText(_("Move mode off"))
			else:
				self["key_green"].setText(_("Move mode on"))
				self["green"].setText(_("Move mode on"))
		else:
			if config.usage.plugins_sort_mode.value == "user":
				self["key_blue"].setText(_("Edit mode on"))
				self["blue"].setText(_("Edit mode on"))
			else:
				self["key_blue"].setText("")
				self["blue"].setText("")
			self["SoftwareActions"].setEnabled(False)
			self["PluginDownloadActions"].setEnabled(True)
			self["key_yellow"].setText("")
			self["yellow"].setText("")
			self["key_red"].setText(_("Remove plugins"))
			self["red"].setText(_("Remove plugins"))
			self["key_green"].setText(_("Download plugins"))
			self["green"].setText(_("Download plugins"))

	def delete(self):
		self.session.openWithCallback(self.PluginDownloadBrowserClosed, PluginDownloadBrowser, PluginDownloadBrowser.REMOVE)

	def download(self):
		self.session.openWithCallback(self.PluginDownloadBrowserClosed, PluginDownloadBrowser, PluginDownloadBrowser.DOWNLOAD, self.firsttime)
		self.firsttime = False

	def PluginDownloadBrowserClosed(self):
		self.updateList()
		self.checkWarnings()

	def openExtensionmanager(self):
		if fileExists(resolveFilename(SCOPE_PLUGINS, "SystemPlugins/SoftwareManager/plugin.py")):
			try:
				from Plugins.SystemPlugins.SoftwareManager.plugin import PluginManager
			except ImportError:
				self.session.open(MessageBox, _("The software management extension is not installed!\nPlease install it."), type = MessageBox.TYPE_INFO,timeout = 10 )
			else:
				self.session.openWithCallback(self.PluginDownloadBrowserClosed, PluginManager)

class PluginDownloadBrowser(Screen):
	DOWNLOAD = 0
	REMOVE = 1
	PLUGIN_PREFIX = 'enigma2-plugin-'
	lastDownloadDate = None

	def __init__(self, session, type = 0, needupdate = True):
		Screen.__init__(self, session)
		
		self.type = type
		self.needupdate = needupdate
		
		self.container = eConsoleAppContainer()
		self.container.appClosed.append(self.runFinished)
		self.container.dataAvail.append(self.dataAvail)
		self.onLayoutFinish.append(self.startRun)
		self.onShown.append(self.setWindowTitle)
		
		self.list = []
		self["list"] = PluginList(self.list)
		self.pluginlist = []
		self.expanded = []
		self.installedplugins = []
		self.plugins_changed = False
		self.reload_settings = False
		self.check_settings = False
		self.install_settings_name = ''
		self.remove_settings_name = ''
		
		if self.type == self.DOWNLOAD:
			self["text"] = Label(_("Downloading plugin information. Please wait..."))
		elif self.type == self.REMOVE:
			self["text"] = Label(_("Getting plugin information. Please wait..."))
		
		self.run = 0
		self.remainingdata = ""
		self["actions"] = ActionMap(["WizardActions"], 
		{
			"ok": self.go,
			"back": self.requestClose,
		})
		if os.path.isfile('/usr/bin/opkg'):
			self.ipkg = '/usr/bin/opkg'
			self.ipkg_install = self.ipkg + ' install'
			self.ipkg_remove =  self.ipkg + ' remove --autoremove' 
		else:
			self.ipkg = 'ipkg'
			self.ipkg_install = 'ipkg install -force-defaults'
			self.ipkg_remove =  self.ipkg + ' remove' 

	def go(self):
		sel = self["list"].l.getCurrentSelection()

		if sel is None:
			return

		sel = sel[0]
		if isinstance(sel, str): # category
			if sel in self.expanded:
				self.expanded.remove(sel)
			else:
				self.expanded.append(sel)
			self.updateList()
		else:
			if self.type == self.DOWNLOAD:
				self.session.openWithCallback(self.runInstall, MessageBox, _("Do you really want to download\nthe plugin \"%s\"?") % sel.name)
			elif self.type == self.REMOVE:
				self.session.openWithCallback(self.runInstall, MessageBox, _("Do you really want to remove\nthe plugin \"%s\"?") % sel.name)

	def requestClose(self):
		if self.plugins_changed:
			plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))
		if self.reload_settings:
			self["text"].setText(_("Reloading bouquets and services..."))
			eDVBDB.getInstance().reloadBouquets()
			eDVBDB.getInstance().reloadServicelist()
		plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))
		self.container.appClosed.remove(self.runFinished)
		self.container.dataAvail.remove(self.dataAvail)
		self.close()

	def resetPostInstall(self):
		try:
			del self.postInstallCall
		except:
			pass

	def installDestinationCallback(self, result):
		if result is not None:
			dest = result[1]
			if dest.startswith('/'):
				# Custom install path, add it to the list too
				dest = os.path.normpath(dest)
				extra = '--add-dest %s:%s -d %s' % (dest,dest,dest)
				Ipkg.opkgAddDestination(dest)
			else:
				extra = '-d ' + dest
			self.doInstall(self.installFinished, self["list"].l.getCurrentSelection()[0].name + ' ' + extra)
		else:
			self.resetPostInstall()
				
	def runInstall(self, val):
		if val:
			if self.type == self.DOWNLOAD:
				if self["list"].l.getCurrentSelection()[0].name.startswith("picons-"):
					supported_filesystems = frozenset(('ext4', 'ext3', 'ext2', 'reiser', 'reiser4', 'jffs2', 'ubifs', 'rootfs'))
					candidates = []
					import Components.Harddisk
					mounts = Components.Harddisk.getProcMounts() 
					for partition in harddiskmanager.getMountedPartitions(False, mounts):
						if partition.filesystem(mounts) in supported_filesystems:
							candidates.append((partition.description, partition.mountpoint)) 
					if candidates:
						from Components.Renderer import Picon
						self.postInstallCall = Picon.initPiconPaths
						self.session.openWithCallback(self.installDestinationCallback, ChoiceBox, title=_("Install picons on"), list=candidates)
					return
				self.install_settings_name = self["list"].l.getCurrentSelection()[0].name
				if self["list"].l.getCurrentSelection()[0].name.startswith('settings-'):
					self.check_settings = True
					self.startIpkgListInstalled(self.PLUGIN_PREFIX + 'settings-*')
				else:
					self.runSettingsInstall()
			elif self.type == self.REMOVE:
				self.doRemove(self.installFinished, self["list"].l.getCurrentSelection()[0].name)

	def doRemove(self, callback, pkgname):
		self.session.openWithCallback(callback, Console, cmdlist = [self.ipkg_remove + Ipkg.opkgExtraDestinations() + " " + self.PLUGIN_PREFIX + pkgname, "sync"], closeOnSuccess = True)

	def doInstall(self, callback, pkgname):
		self.session.openWithCallback(callback, Console, cmdlist = [self.ipkg_install + " " + self.PLUGIN_PREFIX + pkgname, "sync"], closeOnSuccess = True)

	def runSettingsRemove(self, val):
		if val:
			self.doRemove(self.runSettingsInstall, self.remove_settings_name)

	def runSettingsInstall(self):
		self.doInstall(self.installFinished, self.install_settings_name)

	def setWindowTitle(self):
		if self.type == self.DOWNLOAD:
			self.setTitle(_("Downloadable new plugins"))
		elif self.type == self.REMOVE:
			self.setTitle(_("Remove plugins"))

	def startIpkgListInstalled(self, pkgname = PLUGIN_PREFIX + '*'):
		self.container.execute(self.ipkg + Ipkg.opkgExtraDestinations() + " list_installed '%s'" % pkgname)

	def startIpkgListAvailable(self):
		self.container.execute(self.ipkg + Ipkg.opkgExtraDestinations() + " list '" + self.PLUGIN_PREFIX + "*'")

	def startRun(self):
		listsize = self["list"].instance.size()
		self["list"].instance.hide()
		self.listWidth = listsize.width()
		self.listHeight = listsize.height()
		if self.type == self.DOWNLOAD:
			if self.needupdate and not PluginDownloadBrowser.lastDownloadDate or (time() - PluginDownloadBrowser.lastDownloadDate) > 3600:
				# Only update from internet once per hour
				self.container.execute(self.ipkg + " update")
				PluginDownloadBrowser.lastDownloadDate = time()
			else:
				self.run = 1
				self.startIpkgListInstalled()
		elif self.type == self.REMOVE:
			self.run = 1
			self.startIpkgListInstalled()

	def installFinished(self):
		if hasattr(self, 'postInstallCall'):
			try:
				self.postInstallCall()
			except Exception, ex:
				print "[PluginBrowser] postInstallCall failed:", ex
			self.resetPostInstall()
		try:
			os.unlink('/tmp/opkg.conf')
		except:
			pass
		for plugin in self.pluginlist:
			if plugin[3] == self["list"].l.getCurrentSelection()[0].name:
				self.pluginlist.remove(plugin)
				break
		self.plugins_changed = True
		if self["list"].l.getCurrentSelection()[0].name.startswith("settings-"):
			self.reload_settings = True
		self.expanded = []
		self.updateList()
		self["list"].moveToIndex(0)

	def runFinished(self, retval):
		if self.check_settings:
			self.check_settings = False
			self.runSettingsInstall()
			return
		self.remainingdata = ""
		if self.run == 0:
			self.run = 1
			if self.type == self.DOWNLOAD:
				self.startIpkgListInstalled()
		elif self.run == 1 and self.type == self.DOWNLOAD:
			self.run = 2
			from Components import opkg
			pluginlist = []
			self.pluginlist = pluginlist
			for plugin in opkg.enumPlugins(self.PLUGIN_PREFIX):
				if plugin[0] not in self.installedplugins and not plugin[0].endswith('-po'):
					pluginlist.append(plugin + (plugin[0][15:],))
			if pluginlist:
				pluginlist.sort()
				self.updateList()
				self["list"].instance.show()
			else:
				self["text"].setText(_("No new plugins found"))
		else:
			if self.pluginlist:
				self.updateList()
				self["list"].instance.show()
			else:
				self["text"].setText(_("No new plugins found"))

	def dataAvail(self, str):
		#prepend any remaining data from the previous call
		str = self.remainingdata + str
		#split in lines
		lines = str.split('\n')
		#'str' should end with '\n', so when splitting, the last line should be empty. If this is not the case, we received an incomplete line
		if len(lines[-1]):
			#remember this data for next time
			self.remainingdata = lines[-1]
			lines = lines[0:-1]
		else:
			self.remainingdata = ""

		if self.check_settings:
			self.check_settings = False
			self.remove_settings_name = str.split(' - ')[0].replace(self.PLUGIN_PREFIX, '')
			self.session.openWithCallback(self.runSettingsRemove, MessageBox, _('You already have a channel list installed,\nwould you like to remove\n\"%s\"?') % self.remove_settings_name)
			return

		if self.run == 1:
			for x in lines:
				plugin = x.split(" - ", 2)
				# 'opkg list_installed' only returns name + version, no description field
				if len(plugin) >= 2:
					if not plugin[0].endswith('-dev') and not plugin[0].endswith('-staticdev') and not plugin[0].endswith('-dbg') and not plugin[0].endswith('-doc') and not plugin[0].endswith('-src') and not plugin[0].endswith('-meta'):
						if plugin[0] not in self.installedplugins:
							if self.type == self.DOWNLOAD and not plugin[0].endswith('-po'):
								self.installedplugins.append(plugin[0])
							else:
								if len(plugin) == 2:
									plugin.append('')
								plugin.append(plugin[0][15:])
								self.pluginlist.append(plugin)

	def updateList(self):
		list = []
		expandableIcon = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/expandable-plugins.png"))
		expandedIcon = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/expanded-plugins.png"))
		verticallineIcon = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/verticalline-plugins.png"))
		
		self.plugins = {}
		for x in self.pluginlist:
			split = x[3].split('-', 1)
			if len(split) < 2:
				continue
			if not self.plugins.has_key(split[0]):
				self.plugins[split[0]] = []

			self.plugins[split[0]].append((PluginDescriptor(name = x[3], description = x[2], icon = verticallineIcon), split[1], x[1]))

		for x in self.plugins.keys():
			if x in self.expanded:
				list.append(PluginCategoryComponent(x, expandedIcon, self.listWidth))
				list.extend([PluginDownloadComponent(plugin[0], plugin[1], plugin[2], self.listWidth) for plugin in self.plugins[x]])
			else:
				list.append(PluginCategoryComponent(x, expandableIcon, self.listWidth))
		self.list = list
		self["list"].l.setList(list)
