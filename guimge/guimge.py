#!/usr/bin/env python2
# -*- coding: utf-8 -*-
'''
    This file is part of guimge.

    Uploader picture to different imagehosting Copyright (C) 2008 apkawa@gmail.com

    guimge is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    guimge is distributed in the hope that it will be useful,
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
import gobject

from glib import GError

import multiprocessing
import threading
import signal

gtk.gdk.threads_init()

#TODO: Сделать относительные пути импорта
#TODO: Добавить скриншотинг, в качестве опциональной зависимости.
#TODO: Сделать возможность убирания в трей. Реализацию подглядеть в http://code.google.com/p/imageshack-applet/

from uimge.uimge import Uimge, Outprint, Hosts


if not sys.platform == 'win32':
    import pygtk
    pygtk.require('2.0')
    HOME = os.environ['HOME']+os.path.sep

else:
    HOME = os.environ['HOMEDRIVE']+os.environ['HOMEPATH']+os.path.sep
    CONF_FILE = 'guimge.conf'


if __file__.startswith('/usr'):
    DATA_DIR = '/usr/share/guimge/'
    CONF_FILE = os.path.join(HOME,'.config','guimge','guimge.conf')
else:
    _path = os.path.join( os.path.dirname( os.path.dirname( os.path.dirname( os.path.abspath(__file__) ) )), "uimge")
    sys.path.insert(0, _path )
    DATA_DIR = os.path.dirname( os.path.abspath( __file__ ) )
    CONF_FILE = 'guimge.conf'

GLADE_FILE = os.path.join( DATA_DIR,'ui','guimge.ui')
ICONS_DIR = os.path.join( DATA_DIR, 'icons')

UIMGE = Uimge()


GUIMGE = {'version':'0.1.4.6-1',}


#__hosts = UIMGE.hosts()
HOSTS =dict( [(host.host, host ) for host in Hosts.hosts_dict.values()] )

OUTPRINT = Outprint()




_thread_flag = True

import ConfigParser
class gUimge_config:
    conf_default_section = 'main'
    default = { conf_default_section:
                {'host':'radikal.ru'},
        }
    _dict_conf = {}
    _modify = False
    def __init__(self):
        """docstring for __init__"""
        self.conf = ConfigParser.ConfigParser( )
        self._dict_conf.update( self.default )

    def read_conf(self, conf):
        """docstring for read"""
        if os.path.exists( conf ):
            self.conf.read( conf )
            for sec in self.conf.sections():
                for opt in self.conf.options( sec):
                    self._dict_conf[sec].update({ opt: self.conf.get( sec, opt)})
        print "read: ",self._dict_conf

    def save_conf(self, conf):
        """docstring for save"""
        if self._modify:
            for mskey, sval in self._dict_conf.items():
                try:
                    self.conf.add_section( mskey )
                except ConfigParser.DuplicateSectionError:
                    pass
                for key, val in sval.items():
                    self.conf.set( mskey, key, val)

        conf_dir = os.path.split( conf )[0]
        if conf_dir and not os.path.exists(conf_dir):
            os.makedirs( conf_dir)
        self.conf.write( open( conf, 'w+b') )
        print self._dict_conf

    def set_main(self, key, val):
        """docstring for set_main"""
        self._dict_conf[ self.conf_default_section ].update( { key:val } )
        self._modify = True

    def get_main(self, key, _eval=False):
        """docstring for get_main"""
        val = self._dict_conf[ self.conf_default_section ].get(key, None)
        if _eval:
            return eval(str(val))
        else:
            return val

    def del_main(self, key):
        """docstring for del_main"""
        try:
            self.conf.remove_option( self.conf_default_section, key)
        except ConfigParser.NoSectionError:
            pass
        self._dict_conf[self.conf_default_section].pop(key,None)
        self._modify = True
        self


class gUimge:
    result = []
    guimge_icon_ico = gtk.gdk.pixbuf_new_from_file( ICONS_DIR+os.path.sep+'guimge.ico')
    guimge_icon_png = gtk.gdk.pixbuf_new_from_file( ICONS_DIR+os.path.sep+'guimge.png')
    image_mime = ("image/png", "image/jpeg", "image/gif", "image/bmp")
    image_type = ('.png', '.jpe', '.jpg', '.jpeg', '.gif', '.bmp')
    stop = False
    upload_thread = None

    def __init__(self, filenames=None):
        '''
        иницилизация программы
        `filenames` - список файлов
        '''
        #Загрузка конфига.
        self.config = gUimge_config()
        self.config.read_conf( CONF_FILE )
        self.default_host = self.config.get_main('host')
        self.default_modeout = self.config.get_main('modeout')

        self.WidgetsTree = gtk.Builder()
        self.WidgetsTree.add_from_file( GLADE_FILE ) # загрузка ui файла
        conn = {
            # Toolbar 
            'on_FileOpen_clicked': self.on_FileOpen_clicked,
            'on_AddFromFolder_activate': self.on_FolderOpen_clicked,
            'on_UploadButton_clicked': self.on_UploadButton_clicked,
            'on_Clipboard_clicked': self.on_Clipboard_clicked,
            'on_AboutButton_clicked': self.on_AboutButton_clicked,
            "on_ExitButton_clicked": self.exit,
            # FileListPage
            'on_SelectHost_changed': self.on_SelectHost_changed,
            'on_FileListIcons_drag_data_received':self.on_FileListIcons_drag_data_received,
            'on_FileListIcons_drag_motion': self.on_FileListIcons_drag_motion,
            'on_FileListIcons_drag_drop': self.on_FileListIcons_drag_drop,
            'on_FileListIcons_key_press_event': self.on_FileListIcons_key_press_event,
            "on_DeleteSelectedItems_clicked": self.DeleteSelectedItemsFileList,
            'on_ClearFileList_clicked':self.on_ClearFileList_clicked,
            "on_CancelButton_clicked": self.on_CancelButton_clicked,
            # Result Page
            'on_SelectModeOutView_changed': self.on_SelectModeOutView_changed,
            'on_DelimiterSelect_changed': self.update_result_text,
            # Settings Page
            'on_SaveSettings_clicked':self.on_SaveSettings_clicked,
            'on_SaveOnExit_toggled':self.on_SaveOnExit_toggled,
            'on_SelStartDir_file_set':self.on_SelStartDir_file_set,
            'on_CheckLastDir_toggled':self.on_CheckLastDir_toggled,
            # Other
            'gtk_main_quit': self.exit,
            'exit_event': self.exit_event,
            }
        self.WidgetsTree.connect_signals( conn) # подключаем сигналы


        window = self.WidgetsTree.get_object( 'main_window') # основное окно
        if (window):
            window.connect("destroy", gtk.main_quit)
        window.set_icon( self.guimge_icon_ico)
        window.show()

        #Устанавливаем список outprint'a
        result_out = self.WidgetsTree.get_object('SelectModeOutView')
        result_out.set_text_column(0)
        list_store = result_out.get_model()
        list_store.append(['Direct url','None'])
        for k in OUTPRINT.outprint_rules.keys():
            list_store.append(
                    [OUTPRINT.outprint_rules[k]['desc'].replace('Output in ',''),k ]
                    )
        if not self.default_modeout:
            result_out.set_active( 0 )
        else:
            _active = OUTPRINT.outprint_rules.keys().index( self.default_modeout )
            result_out.set_active( _active )

        #Устанавливаем разделитель.
        self.delim = self.WidgetsTree.get_object('DelimiterSelect')
        self.delim.set_text_column(0)
        self.delim.append_text('\\n')
        self.delim.set_active(0)


        #Чтение и определение стартовой директории.
        _sd = self.config.get_main( 'startdir')
        _ld = self.config.get_main( 'lastdir' )
        if _ld:
            self.lastdir = _ld
            print self.lastdir
            self.WidgetsTree.get_object('CheckLastDir').set_active(True)
            self.WidgetsTree.get_object('SelStartDir').set_sensitive(False)
        elif _sd:
            self.lastdir = 'file://'+_sd
        else:
            self.lastdir = 'file://'+HOME

        #Виджеты
        self.result_text = self.WidgetsTree.get_object('ResultText')
        self.upload_button = self.WidgetsTree.get_object('UploadButton')
        self.abort_button  = self.WidgetsTree.get_object("AbortButton")

        self.filelistprogress = self.WidgetsTree.get_object('progressbar1')
        self.cancelbutton = self.WidgetsTree.get_object( "CancelButton" )
        self.uploadprogressvbox = self.WidgetsTree.get_object("uploadprogressvbox")
        self.statusbar = self.WidgetsTree.get_object( "statusbar1" )
        #установка опций.
        self.WidgetsTree.get_object('SaveOnExit').set_active( self.config.get_main('save_on_exit', _eval=True) or False )
        self.WidgetsTree.get_object('SelStartDir').set_current_folder_uri(self.lastdir)


        self.initSelectHost() # создаем список хостингов
        self.initFileListIcons( filenames) # создаем виджет списка файлов


    def initFileListIcons(self, filenames=None):
        '''
        Create File List
        '''
        self.store = gtk.ListStore( str,             # path
                                     gtk.gdk.Pixbuf, # thumb pic
                                     str,            # title
                                     long,           # size
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
        def get_favicon( host, ico_path):
            if not os.path.exists(ico_path):
                import urllib
                u = urllib.urlopen('http://favicon.yandex.net/favicon/%s'%host).read()
                #http://www.google.com/s2/favicons?domain=www.labnol.org
                with open( '/tmp/tmp.png','w+b') as tmp:
                    tmp.write( u )
                tmp_ico = gtk.gdk.pixbuf_new_from_file("/tmp/tmp.png")
                try:
                    if tmp_ico.get_width() == 1:
                        _ico = fail_icon
                        fail_icon.save( ico_path, "png" )
                    else:
                        _ico = tmp_ico.scale_simple( 16,16, gtk.gdk.INTERP_HYPER)
                        tmp_ico.save( ico_path,"png" )
                except GError:
                    _ico = fail_icon
            else:
                _ico = gtk.gdk.pixbuf_new_from_file( ico_path)

            return _ico

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

        fail_icon = self.guimge_icon_ico.scale_simple(16,16, gtk.gdk.INTERP_HYPER)

        ico_dir = os.path.join( ICONS_DIR, 'hosts')
        hosts = sorted( HOSTS.keys() )
        for host in hosts:
            ico_name = host+'.png'
            ico_path = os.path.join( ico_dir,ico_name)
            #_ico = gtk.gdk.pixbuf_new_from_file_at_size( os.path.join(ico_dir, old_ico_name), 16,16)
            #_ico.save( ico_path,"png")
            ico = get_favicon( host, ico_path )

            list_store.append( [ico, host] )

        _active = hosts.index( self.default_host)

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
        self.uploadprogressvbox.show()
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
            if self.stop:
                break
            self.filelistprogress.set_text(
                   'Added %i file of %i files'%( current_file_count, all_files_count)
                   )
            self.filelistprogress.set_fraction( float( current_file_count )/ all_files_count )
            while gtk.events_pending():
                gtk.main_iteration()

            self._add_file(f)
            # gtk.gdk.threads_leave()
            current_file_count += 1

        self.stop = False
        self.uploadprogressvbox.hide()

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

        self.upload_button.set_sensitive(noclear)
        self.WidgetsTree.get_object('ClearFileList').set_sensitive(noclear)
        self.WidgetsTree.get_object('DeleteSelectedItems').set_sensitive(noclear)

    def _uploading(self, obj):
        """docstring for _uploading"""
        def upload_thread( obj, thread_result):
            global UIMGE
            UIMGE.upload( unicode( obj,"utf-8") )
            thread_result += (       UIMGE.img_url,
                    UIMGE.img_thumb_url,
                    UIMGE.filename
                    )

        if sys.platform != "win32":
            manager = multiprocessing.Manager()
            thread_result = manager.list()
            self.upload_thread = multiprocessing.Process( target=upload_thread, args=(obj,thread_result) )
            self.upload_thread.start()

            while self.upload_thread.is_alive():
                gtk.main_iteration()
                if self.stop:
                    self.filelistprogress.set_text("Stopped...")
                    self.upload_thread.terminate()
                    break
            return thread_result
        else:
            global UIMGE
            UIMGE.upload( unicode( obj,"utf-8") )

            _result = ( UIMGE.img_url,
                            UIMGE.img_thumb_url,
                            UIMGE.filename
                            )


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

        self.upload_button.hide()
        self.abort_button.show()
        self.uploadprogressvbox.show()

        objects = [ s[0] for s in self.store]
        self.result = []
        self.stop = False
        if objects:
            print "Upload!"
            __current_n_obj = 1
            __all_n_obj = len(objects)
            for obj in objects:
                self.filelistprogress.set_text(
                       'Uploading %i file of %i files'%( __current_n_obj, __all_n_obj)
                       )
                self.filelistprogress.set_fraction( float(__current_n_obj)/__all_n_obj )
                while gtk.events_pending():
                    gtk.main_iteration()
                __current_n_obj +=1

                _result = self._uploading( obj)
                if self.stop:
                    break
                self.result.append( _result  )
                self.update_result_text()
                self.WidgetsTree.get_object('Clipboard').set_sensitive(True)

            self.stop = False
            self.uploadprogressvbox.hide()
            self.abort_button.hide()
            self.upload_button.show()

    def on_AboutButton_clicked(self, widget):
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
        self.config.set_main('host', self.current_host)
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

    def on_CancelButton_clicked( self, widget):
        self.stop = True

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
        self.on_CheckLastDir_toggled()
        self.config.set_main( 'host',self.current_host)
        self.config.set_main( 'modeout',self.current_modeout )
        self.config.save_conf( CONF_FILE )
        pass

    def on_SaveOnExit_toggled(self, widget):
        """docstringfname for on_SaveOnExit_toggled"""
        self.config.set_main('save_on_exit', widget.get_active())

    def on_SelStartDir_file_set(self, widget):
        """docstring for on_SelStartDir_file_set"""
        startdir = widget.get_filename()
        self.config.set_main('startdir', startdir)
        self.lastdir = 'file://'+startdir
    def on_CheckLastDir_toggled(self, widget=None):
        """docstring for on_CheckLastDir_toggled"""
        active =widget.get_active() if widget else self.WidgetsTree.get_object('CheckLastDir').get_active()
        if active:
            self.config.set_main('lastdir', self.lastdir)
            self.WidgetsTree.get_object('SelStartDir').set_sensitive( False)
        else:
            self.config.del_main('lastdir')
            self.WidgetsTree.get_object('SelStartDir').set_sensitive( True)

    def exit_event(self, widget, event):
        print widget
        print event.keyval
        if event.keyval == 65307:
            self.exit()

    def exit( self, widget=None):
        if self.upload_thread:
            self.upload_thread.terminate()
        if self.config.get_main( 'save_on_exit', _eval=True):
            self.config.save_conf( CONF_FILE)
        gtk.main_quit()


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

    gtk.gdk.threads_enter()
    gtk.main()
    gtk.gdk.threads_leave()

if __name__ == "__main__":
    main()
