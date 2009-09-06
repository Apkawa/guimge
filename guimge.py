#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
    This file is part of uimge.

    Uploader picture to different imagehosting Copyright (C) 2008 apkawa@gmail.com

    uimge is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

    site project http://wiki.github.com/Apkawa/uimge
'''

import sys
import os



import gtk
import gtk.glade
import gobject

import threading

#gtk.gdk.threads_init()

#TODO: Сделать относительные пути импорта
#TODO: Добавить скриншотинг, в качестве опциональной зависимости.
#TODO: Сделать возможность убирания в трей. Реализацию подглядеть в http://code.google.com/p/imageshack-applet/

sys.path.insert(0, os.path.abspath("..") )
from uimge import Uimge, Outprint, Hosts


if not sys.platform == 'win32':
    import pygtk
    pygtk.require('2.0')
    HOME = os.environ['HOME']+os.path.sep

else:
    HOME = os.environ['HOMEDRIVE']+os.environ['HOMEPATH']+os.path.sep
    CONF_FILE = 'guimge.conf'


if __file__.startswith('/usr/bin/'):
    DATA_DIR = '/usr/share/guimge/'
    CONF_FILE = os.path.join(HOME,'.guimge','guimge.conf')
else:
    DATA_DIR = ''
    CONF_FILE = 'guimge.conf'

GLADE_FILE = '%sguimge.glade'%DATA_DIR
ICONS_DIR = '%sicons'%DATA_DIR

UIMGE = Uimge()



GUIMGE = {'version':'0.1.4.5-1',}


#__hosts = UIMGE.hosts()
HOSTS =dict( [(host.host, host ) for host in Hosts.hosts_dict.values()] )

OUTPRINT = Outprint()

class gUimge:
    lastdir = 'file://'+HOME
    result = []
    guimge_icon_ico = gtk.gdk.pixbuf_new_from_file( ICONS_DIR+os.path.sep+'guimge.ico')
    guimge_icon_png = gtk.gdk.pixbuf_new_from_file( ICONS_DIR+os.path.sep+'guimge.png')
    image_mime = ("image/png", "image/jpeg", "image/gif", "image/bmp")
    image_type = ('.png', '.jpe', '.jpg', '.jpeg', '.gif', '.bmp')

    def __init__(self, filenames=None):
        from ConfigParser import ConfigParser
        self.conf = ConfigParser( )#
        self.conf_default_section = 'defaults'
        if os.path.exists( CONF_FILE ):
            self.conf.read( CONF_FILE)
        else:
            print 'Not found config'
            _defaults={'host':'radikal.ru', 'modeout': 'False',"proxy":""}
            self.conf.add_section( self.conf_default_section )
            for key, val in _defaults.items():
                self.conf.set( self.conf_default_section, key, val)
        self.default_host = self.conf.get( self.conf_default_section, 'host')
        self.default_modeout = self.conf.get( self.conf_default_section, 'modeout')
        #print self.conf.items( self.conf_default_section)

        self.WidgetsTree = gtk.Builder()
        self.WidgetsTree.add_from_file( GLADE_FILE )
        conn = {
            # Toolbar 
            'on_FileOpen_clicked': self.on_FileOpen_clicked,
            'on_AddFromFolder_activate': self.on_FolderOpen_clicked,
            'on_UploadButton_clicked': self.on_UploadButton_clicked,
            'on_Clipboard_clicked': self.on_Clipboard_clicked,
            'on_About_clicked': self.on_About_clicked,
            # 'on_SettingsToggle_toggled': self.on_SettingsToggle_toggled,
            # FileListPage
            'on_SelectHost_changed': self.on_SelectHost_changed,
            'on_FileListIcons_drag_data_received':self.on_FileListIcons_drag_data_received,
            'on_FileListIcons_drag_motion': self.on_FileListIcons_drag_motion,
            'on_FileListIcons_drag_drop': self.on_FileListIcons_drag_drop,
            'on_FileListIcons_key_press_event': self.on_FileListIcons_key_press_event,
            "on_DeleteSelectedItems_clicked": self.DeleteSelectedItemsFileList,
            'on_ClearFileList_clicked':self.on_ClearFileList_clicked,
            # Result Page
            'on_SelectModeOutView_changed': self.on_SelectModeOutView_changed,
            'on_DelimiterSelect_changed': self.update_result_text,
            # Settings Page
            'on_SaveSettings_clicked':self.on_SaveSettings_clicked,
            # Other
            'gtk_main_quit': gtk.main_quit,
            'exit_event': self.exit_event,
            }
        self.WidgetsTree.connect_signals( conn)

        window = self.WidgetsTree.get_object( 'gUimge_multiple')
        if (window):
            window.connect("destroy", gtk.main_quit)
        window.set_icon( self.guimge_icon_ico)
        window.show()


        self.initSelectHost()
        self.initFileListIcons( filenames)

        #Устанавливаем список outprint'a
        result_out = self.WidgetsTree.get_object('SelectModeOutView')
        result_out.set_text_column(0)
        list_store = result_out.get_model()
        list_store.append(['Direct url','False'])
        for k in OUTPRINT.outprint_rules.keys():
            list_store.append(
                    [OUTPRINT.outprint_rules[k]['desc'].replace('Output in ',''),k ]
                    )
        if self.default_modeout == 'False':
            result_out.set_active( 0 )
        else:
            _active = OUTPRINT.outprint_rules.keys().index( self.default_modeout )
            result_out.set_active( _active )

        #Устанавливаем разделитель.
        self.delim = self.WidgetsTree.get_object('DelimiterSelect')
        self.delim.set_text_column(0)
        self.delim.append_text('\\n')
        self.delim.set_active(0)

        self.result_text = self.WidgetsTree.get_object('ResultText')

        #Виджеты
        self.filelistprogress = self.WidgetsTree.get_object('progressbar1')
        self.statusbar = self.WidgetsTree.get_object( "statusbar1" )

        self._check_filelist_state()

    def initFileListIcons(self, filenames):
        self.store = gtk.ListStore( str, # path
                                    gtk.gdk.Pixbuf, #thumb
                                    str, # title
                                    long, # size
                                    )
        icon_list = self.WidgetsTree.get_object('FileListIcons')
        icon_list.set_model( self.store)
        icon_list.set_pixbuf_column(1)
        icon_list.set_text_column(2)
        self.dnd_list = [ ( 'text/uri-list', 0, 80 ),
                ]
        icon_list.drag_dest_set(
                gtk.DEST_DEFAULT_DROP ,
                self.dnd_list,
                gtk.gdk.ACTION_COPY)
        if filenames:
            self._add_files(filenames)
            self._check_filelist_state()

    def initSelectHost(self):
        "Устанавливаем выпадающий список выбора хостингов c иконостасом"
        self.SelectHost = self.WidgetsTree.get_object("SelectHost")
        list_store = gtk.ListStore( gtk.gdk.Pixbuf, str)
        self.SelectHost.set_model( list_store)

        crp = gtk.CellRendererPixbuf()
        self.SelectHost.pack_start(crp,False,)
        self.SelectHost.add_attribute(crp, 'pixbuf', 0)
        crt = gtk.CellRendererText()
        self.SelectHost.pack_start(crt,False)
        self.SelectHost.add_attribute(crt, 'text', 1)

        for host in HOSTS.keys():
            ico_name = host+'.ico'
            ico_dir = os.path.join ( ICONS_DIR, 'hosts')
            ico_path = os.path.join( ico_dir,ico_name)

            if not os.path.exists(ico_path):
                import urllib
                u = urllib.urlopen('http://%s/favicon.ico'%host)
                print ico_path
                t = open( ico_path, 'w+b')
                t.write(u.read())
                t.close()
            try:
                ico = gtk.gdk.pixbuf_new_from_file_at_size( ico_path, 16,16)
            except:
                ico = self.guimge_icon_ico.scale_simple(16,16, gtk.gdk.INTERP_HYPER)
            self.SelectHost.get_model().append( [ico, host] )
        _active = HOSTS.keys().index( self.default_host)
        #print self.default_host
        self.SelectHost.set_active( _active  )

    def _add_file(self, filename):
        "Фукнция добавления файла в iconview"
        thumb_size=100
        f = unicode(filename,'utf-8')
        filename =  os.path.split(f)[1]
        image_info = gtk.gdk.pixbuf_get_file_info(f)

        size = os.stat(f).st_size
        size_str = human( size )
        if os.path.splitext(f)[1][1:] in self.image_type or image_info:
            image_size = ' %sx%s'%( image_info[1], image_info[2],)
            image_mime=   ' '.join( image_info [0]['mime_types'])
        else:
            print filename
            return False

        if len(filename) > 31:
            filename = '%s...%s'%(
                    filename[0:15],filename[-15:],
                    )
        else:
            filename = '%s'%(
                    filename,
                    )

        try:
            if image_info[1] >= thumb_size or image_info[1] >= thumb_size:
                pixbuf = gtk.gdk.pixbuf_new_from_file_at_size( f, thumb_size, thumb_size)
            else:
                pixbuf = gtk.gdk.pixbuf_new_from_file( f)
        except:
            'Stock pixbuf'
            _t = gtk.TreeView()
            pixbuf = _t.render_icon(
                    gtk.STOCK_MISSING_IMAGE,
                    gtk.ICON_SIZE_DIALOG,
                    None)
        title = '%s %s %s\n%s'%( image_size, image_mime, size_str, filename)
        self.store.append([f, pixbuf, title, size])

    def _add_files(self, filenames):

        self.filelistprogress.show()
        file_list = []
        for f in filenames:
            if not os.path.isdir(f):
                file_list.append(f)
            else:
                for filename in os.listdir( f ):
                    path = os.path.join( f, filename)
                    if os.path.isfile( path ):
                        file_list.append( path )
        all_files_count = len( file_list )
        current_file_count = 0

        for f in file_list:
            # gtk.gdk.threads_enter()
            self.filelistprogress.set_text(
                   'Added %i file of %i files'%( current_file_count, all_files_count)
                   )
            self.filelistprogress.set_fraction( float( current_file_count )/ all_files_count )
            while gtk.events_pending():
                gtk.main_iteration()

            self._add_file(f)
            # gtk.gdk.threads_leave()
            current_file_count += 1
        self.filelistprogress.hide()

    def _check_filelist_state(self):
        _store =  [ s[3] for s in self.store]
        if not _store:
            noclear=False
        else:
            count = len( _store )
            sum_size =  human( sum( _store ) )
            # count_label = self.WidgetsTree.get_object( "count_files" )
            # sum_size_label    = self.WidgetsTree.get_object( "sum_size" )
            # count_label.set_label( str(count))
            # sum_size_label.set_label( sum_size )
            state_str = "%i images (%s)"%( count, sum_size)
            _id = self.statusbar.get_context_id("FileListState")
            self.statusbar.push( _id , state_str )
            noclear=True

        self.WidgetsTree.get_object('UploadButton').set_sensitive(noclear)
        self.WidgetsTree.get_object('ClearFileList').set_sensitive(noclear)
        self.WidgetsTree.get_object('DeleteSelectedItems').set_sensitive(noclear)

    #Events
    #Toolbar
    def on_FileOpen_clicked(self, widget, folder=False):
        print self.lastdir
        chooser = FileChooser(self.lastdir, folder_chooser = folder)
        chooser.set_select_multiple(True)
        resp = chooser.run()
        print resp
        if resp == gtk.RESPONSE_OK:
            __files =  chooser.get_filenames()
            self.lastdir = chooser.get_current_folder_uri()
            chooser.destroy()
            #print __files
            self._add_files(filenames=__files)
            self._check_filelist_state()
        elif resp == gtk.RESPONSE_CANCEL:
            chooser.destroy()
            print 'Closed, no files selected'

    def on_UploadButton_clicked(self, widget):
        objects = [ s[0] for s in self.store]
        self.result = []
        if objects:
            print "Upload!"
            __current_n_obj = 1
            __all_n_obj = len(objects)
            for obj in objects:
                self.filelistprogress.show()
                self.filelistprogress.set_text(
                       'Uploading %i file of %i files'%( __current_n_obj, __all_n_obj)
                       )
                self.filelistprogress.set_fraction( float(__current_n_obj)/__all_n_obj )
                __current_n_obj +=1

                while gtk.events_pending():
                    gtk.main_iteration()

                state = UIMGE.upload( unicode(obj, 'utf-8') )
                if state:
                    self.result.append( (
                        UIMGE.img_url,
                        UIMGE.img_thumb_url,
                        UIMGE.filename
                        ) )
                    #print self.result
                    self.update_result_text()
                    #self.WidgetsTree.get_object('ResultExpander').set_sensitive(True)
                    self.WidgetsTree.get_object('Clipboard').set_sensitive(True)
            self.filelistprogress.hide()

    def on_About_clicked(self, widget):
        about = self.WidgetsTree.get_object('About')
        about.set_logo( self.guimge_icon_png)
        about.set_icon( self.guimge_icon_ico )
        about.set_version( GUIMGE['version'])
        about.run()
        about.hide()

    def on_FolderOpen_clicked(self, widget):
        self.on_FileOpen_clicked( widget, folder=True)

    def on_Clipboard_clicked(self, widget):
        result = self.make_result()
        _clip = gtk.Clipboard()
        _clip.clear()
        _clip.set_text( result )


    # FileList Page
    def DeleteSelectedItemsFileList( self, widget=None):
        _widget = self.WidgetsTree.get_object("FileListIcons")
        selection = _widget.get_selected_items()
        #print selection
        for s in selection:
            self.store.remove( _widget.get_model().get_iter( s[0] ) )
        self._check_filelist_state()

    def on_SelectHost_changed(self, widget):
        self.current_host = widget.get_model()[widget.get_active()][1]
        UIMGE.set_host( HOSTS.get( self.current_host ))
        #print "sel host"
        #print widget.get_active(),widget.get_model()[widget.get_active()][1], widget.name
        #print self.current_host

    def on_FileListIcons_drag_data_received( self, widget, context, x, y, selection, target_type, timestamp):
        "Drag-n-drop"
        if target_type == 80:
            from urllib import unquote
            uri = selection.data.strip()
            files= uri.split()
            self._add_files(
                    [unquote(os.path.normpath(f).replace('file:',''))
                        for f in files]
                    )
            self._check_filelist_state()

    def on_FileListIcons_drag_motion(self,widget, context, x, y, time):
        context.drag_status(gtk.gdk.ACTION_COPY, time)
        return True

    def on_FileListIcons_drag_drop(self,widget, context, x, y, time):
        context.finish(True, False, time)

    def on_FileListIcons_key_press_event(self,widget, event=None):
        #print event.hardware_keycode
        #print event.keyval
        if event.keyval == 65535:
            self.DeleteSelectedItemsFileList()

    def on_ClearFileList_clicked(self, widget):
        self.store.clear()
        self._check_filelist_state( )

    #Result Page
    def on_SelectModeOutView_changed( self, widget):
        #print widget.get_active(),widget.get_active_text(), widget.name
        if widget.get_active() != -1:
            key_out = widget.get_model()[widget.get_active()][1]
            #print key_out
            self.current_modeout = key_out
            OUTPRINT.set_rules(key_out)
        else:
            #print widget.get_active_text()
            self.current_modeout = ''
            OUTPRINT.set_rules(usr=widget.get_active_text())
        self.update_result_text()

    def update_result_text(self, widget=None):
        _result = self.make_result()
        if _result:
            self.result_text.get_buffer().set_text( _result)
            return True
        else:
            return False

    def make_result(self):
        try:
            _delim = self.delim.get_active_text().replace('\\n','\n')
        except AttributeError:
            _delim = '\n'
        return _delim.join([OUTPRINT.get_out( r[0], r[1], r[2]) for r in self.result] )

    #Settings page
    def on_SaveSettings_clicked(self, widget):
        self.conf.set( self.conf_default_section ,'host',self.current_host)
        self.conf.set( self.conf_default_section ,'modeout',self.current_modeout)
        conf_dir = os.path.split( CONF_FILE)[0]
        if conf_dir and not os.path.exists(conf_dir):
            os.makedirs( conf_dir)
        self.conf.write( open(CONF_FILE, 'w+b') )
        pass

    def exit_event(self, widget, event):
        print widget
        print event.keyval
        if event.keyval == 65307:
            gtk.main_quit()

    # def on_SettingsToggle_toggled(self, widget):
    #     settings_vbox = self.WidgetsTree.get_object('SettingVBox')
    #     if widget.get_active():
    #         settings_vbox.show()
    #     else:
    #         settings_vbox.hide()


def FileChooser(lastdir=False, folder_chooser=False):
    chooser = gtk.FileChooserDialog(
            title="Select image",
            action=gtk.FILE_CHOOSER_ACTION_OPEN if not folder_chooser else gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            buttons=(
                gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,
                gtk.STOCK_OPEN,gtk.RESPONSE_OK),
                              )
#http://www.pygtk.org/pygtk2tutorial/sec-FileChoosers.html
#        http://pygtk.org/docs/pygtk/class-gtkfilechooser.html
    #Set filters
    list_filters = (
            ("Images",(
                ("image/png","image/jpeg", "image/gif","image/bmp"),
                ("*.png","*.jpg","*.jpeg","*.gif","*.tif","*.tiff","*.bmp") ) ),
            ("PNG",(
                ("image/png",),
                ("*.png",) ) ),
            ("JPG/JPEG",(
                ("image/jpeg",),
                ("*.jpg","*.jpeg",) ) ),
            ("GIF",(
                ("image/gif",),
                ("*.gif",) ) ),
            ("BMP",(
                ("image/bmp",),
                ("*.bmp",) ) ),
            )

    for f_name, filtr in list_filters:
        _filter = gtk.FileFilter()
        _filter.set_name( f_name )
        for f_mime in filtr[0]:
            _filter.add_mime_type(f_mime)
        for f_pattern in filtr[1]:
            _filter.add_pattern( f_pattern)
        chooser.add_filter(_filter)
    #Set prewiew
    def update_preview( file_chooser, prewiew):
        filename = file_chooser.get_preview_filename()
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size( filename, 200, 200)
            prewiew.set_from_pixbuf( pixbuf)
            have_preview = True
        except:
            have_preview = False
        file_chooser.set_preview_widget_active(have_preview)
        return
    if lastdir:
        chooser.set_current_folder_uri( lastdir )

    preview = gtk.Image()
    chooser.set_preview_widget( preview )
    chooser.connect("update-preview", update_preview ,preview )
    return chooser


def human(num, prefix=" ", suffix='b'):
    num=float(num)
    for x in ['','K','M','G','T']:
        if num<1024:
            return "%3.1f%s%s%s" % (num, prefix, x,  suffix)
        num /=1024


def main():
    from optparse import OptionParser
    parser= OptionParser()
    (options, args) = parser.parse_args()
    app = gUimge( filenames=args)

    # gtk.gdk.threads_enter()
    gtk.main()
    # gtk.gdk.threads_leave()

if __name__ == "__main__":
    # gtk.gdk.threads_init()
    main()

