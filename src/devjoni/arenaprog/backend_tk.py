'''Tkinter (tcl/tk) backend.
'''

import tkinter as tk

from .common import (
        CommonMainBase,
        CommonWidgetBase,
        common_build_image,
        )
from .imagefuncs import rgb2hex

class GuiBase:
    '''Common methods for the widgets and the main window.
    '''
    def after(self, millis, function):
        '''Schedules a function to be ran milliseconds later.
        '''
        return self.tk.after(millis, function)
    
    def destroy(self):
        self.tk.destroy()
   

class MainWindow(CommonMainBase, GuiBase):
    '''Creates a main window (the root "widget").
    - fullscreen=True sets the window in full screen
    - Position and dimention of the window can be set with window_geom with a format 'WidthxHeight+X+Y'.
        X and Y coordinated can be omited (pass only 'WidthxHeight').
    '''

    TK = []

    def __init__(self, parent=None, frameless=False, fullscreen=False,window_geom="800x600"):
        super().__init__()
        
        if parent is None:
            self.tk = tk.Tk()
            self.TK.append(self.tk)
        else:
            self.tk = tk.Toplevel(self.TK[0])

        self._title = ''

        if frameless:
            self.tk.overrideredirect(True)
            self.tk.attributes('-topmost', False)
        
        self.geometry = window_geom

        if fullscreen:
            self.tk.attributes("-fullscreen", True)
        
        

    def run(self):
        '''Runs 
        '''
        super().run()
        self.tk.update() #testing code
        print(self.tk.winfo_width(), self.tk.winfo_height(),self.tk.winfo_x(),self.tk.winfo_y()) #testing code
        self.tk.mainloop()
        self.running = False
        
        

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, name):
        self.tk.title(name)
        self._title = name

    @property
    def screen_width(self):
        return self.tk.winfo_screenwidth()
    
    @property
    def screen_height(self):
        return self.tk.winfo_screenheight()
    
    @property
    def geometry(self):
        string = self.tk.geometry()
        width, height = string.split('x')
        if '+' in height: #check if user passed a x and y coordinates (that requires 2 '+' in the format widthxheight+x+y)
            if height.count('+')==2: #check there is indeed 2 '+' and extract the cordinates and the heights
                height, x, y = height.split('+')
                return int(width), int(height), int(x), int(y)
            else:
                height = height.split('+')[0] #we keep the height
                return int(width), int(height), None, None
        else:
            return int(width), int(height), None, None


    @geometry.setter
    def geometry(self,string):
        width, height, x, y = super().parse_geometry(string)
        string = f'{width}x{height}'
        if x is not None and y is not None:
            string += f'+{x}+{y}'
        self.tk.geometry(string)
    
    def withdraw(self):
        self.tk.withdraw()

    def get_backend_info(self):
        return {'name': 'tk'}
    
    


class WidgetBase(GuiBase, CommonWidgetBase):
    '''Common base class for all widgets.

    For basis of your own more complex widgets, it is better to use
    FrameWidget for example (unless you know what you do).

    Attributes
    ----------
    parent : object
        The parent widget or window.
    '''
    def __init__(self, parent):
        self.parent = parent
        
        self._hidden = False
        self._gridded = False
        self._grid_options = None
    
    def grid(self, row=0, column=0, sticky='NSWE',
             columnspan=1, rowspan=1,
             column_weight=1, row_weight=1):
        
        if self._hidden:
            self._grid_options = [row, column, sticky, columnspan,
                                  rowspan, column_weight, row_weight]
            return
        self._gridded = True
        self._grid_options = None

        left,right,top,bottom = self.margins

        self.tk.grid(
                row=row, column=column, sticky=sticky,
                columnspan=columnspan, rowspan=rowspan,
                padx=(left, right), pady=(top, bottom))
        
        self.parent.tk.columnconfigure(column, weight=column_weight)
        self.parent.tk.rowconfigure(row, weight=row_weight)

    def set_command(self, command):
        if not callable(command):
            raise ValueError('Command has to be callable')
        self.command = command
        try:
            self.tk.configure(command=self._command_wrapper)
        except:
            pass


    def grid_remove(self):
        self.tk.grid_remove()
        self._gridded = False
    
    def set(self, text=None, bg=None, active_bg=None, resize_handler=None,
            leftclick_handler=None, rightclick_handler=None,
            enter_handler=None, exit_handler=None):
        '''Configure extra settings supported by all widgets.

        Setting a parameter to None makes no changes to the setting
        and setting it False disables or sets the setting to its
        default value.

        text : string
            Sets the text label
        bg, active_bg : string or list/tuple?
            Sets the background colour
        resize_handler : callable or False
            Called when the widget is being resized
        leftclick_handler, rightclick_handler : callable or False
            When left and rightclick are pressed over the widget.
            It is better to use a command where applicable.
        enter_handler, exit_handler : callable or False
            When mouse comes to hover over and leaves
        '''
        if text is not None:
            self.tk.configure(text=text)
        if bg is not None:
            self.tk.configure(bg=bg)
        if active_bg is not None:
            self.tk.configure(activebackground=active_bg)
        if resize_handler is not None:
            if not callable(resize_handler):
                raise ValueError('Resize handler has to be callable')
            self.resize_handler = resize_handler
            self.tk.bind('<Configure>', self._resize_handler_wrapper)
        if leftclick_handler is not None:
            #self.leftclick_handler = leftclick_handler
            self.tk.bind('<Button-1>', leftclick_handler)
        if rightclick_handler is not None:
            self.tk.bind('<Button-3>', rightclick_handler)
        if enter_handler is not None:
            self.tk.bind('<Enter>', enter_handler)
        if exit_handler is not None:
            self.tk.bind('<Enter>', exit_handler)
    
    def get(self, key):
        return self.tk.cget(key)
    
    def set_visibility(self, showed):
        if showed:
            self._hidden = False
            if self._gridded:
                return
            if self._grid_options is None:
                self.tk.grid()
                self._gridded = True
            else:
                self.grid(*self._grid_options)
        else:
            self._hidden = True
            if not self._gridded:
                return
            self.tk.grid_remove()
            self._gridded = False

    def _resize_handler_wrapper(self, event):
        width = self.tk.winfo_width()
        height = self.tk.winfo_height()
        self.resize_handler(width, height)


    def grab_focus(self):
        self.tk.focus_set()


class InputWidgetBase(WidgetBase):
    '''Common base class for all widgets taking in user input.
    '''

    def __init__(self, parent):
        super().__init__(parent)
    
    def get_input(self):
        '''Returns the state of the current value.
        '''
        return self.tk.get()

    def set_input(self, text):
        self.tk.delete(0, tk.END)
        self.tk.insert(0, text)



    def _command_wrapper(self, arg):
        self.command(arg)


class FrameWidget(WidgetBase):
    def __init__(self, parent):
        super().__init__(parent)
        self.tk = tk.Frame(parent.tk)

class ScrollableFrame(FrameWidget):
    # TODO Scrollable frame for tkinter
    pass

class TextWidget(WidgetBase):
    def __init__(self, parent, text=''):
        super().__init__(parent)
        self.tk = tk.Label(parent.tk, text=text)

class ButtonWidget(WidgetBase):
    def __init__(self, parent, text='', command=None):
        super().__init__(parent)
        self.tk = tk.Button(parent.tk, text=text, command=command)
    
    def set_command(self, command):
        self.tk.configure(command=command)


class SliderWidget(InputWidgetBase):
    def __init__(self, parent, from_=0, to=1, resolution=None,
                 horizontal=True):
        super().__init__(parent)

        if horizontal:
            orient = tk.HORIZONTAL
        else:
            orient = tk.VERTICAL

        if resolution is None:
            resolution = (to-from_)/100

        self.tk = tk.Scale(
                parent.tk, from_=from_, to=to,
                resolution=resolution, orient=tk.HORIZONTAL)

    def set_input(self, value):
        pass

    def get_input(self):
        pass

class EntryWidget(InputWidgetBase):
    def __init__(self, parent, on_enter=None):
        super().__init__(parent)
        self.tk = tk.Entry(parent.tk)
        
        if on_enter:
            self._enter_command = on_enter
            self.tk.bind('<Return>', self._on_enter_wrapper)

    def _on_enter_wrapper(self, arg):
        self._enter_command(self.get_input())


class EditorWidget(InputWidgetBase):
    '''Multiline text editor.

    Uses tkinter Text widget.
    '''
    def __init__(self, parent):
        super().__init__(parent)
        self.tk = tk.Text(parent.tk)

    def set(text=None, **kwargs):
        # Edit here so that we can use the text configuration
        # option to retrieve the text.
        if text is not None:
            self.tk.set(text)
        super().set(**kwargs)
    
    def get_input(self):
        return self.tk.get("1.0", tk.END)

    def set_input(self, text):
        self.tk.delete("1.0", tk.END)
        self.tk.insert("1.0", text)

    def set_insert_location(self, row, column):
        index = f'{row+1}.{column+1}'
        self.tk.mark_set('insert', index)
        self.tk.see(index)

    def get_insert_location(self):
        row, column = self.tk.index('insert').split('.')
        return int(row)-1, int(column)-1


class DropdownWidget(InputWidgetBase):
    '''Bad widget, goes against design principles. Do not use.
    '''
    def __init__(self, parent, default, values):
        super().__init__(parent)
        self.tk_stringvar = tk.StringVar()
        self.tk = tk.OptionMenu(
                parent.tk, self.tk_stringvar, default, values)
    
    def get_input(self):
        return self.tk_stringvar.get()



class ImageImage:
    '''Contains the actual image
    '''
    def __init__(self, fn=None, width=None, height=None):
        if fn is not None:
            self.tk = tk.PhotoImage(file=fn)
        else:
            self.tk = tk.PhotoImage(width=width, height=height)

    def set_from_rgb(self, image):
        self.set_from_hex(rgb2hex(image))

    def set_from_hex(self, image):

        h = min((len(image)), self.tk.height())
        w = min((len(image[0])), self.tk.width()) 
        for j in range(0,h):
            self.tk.put(image[j], to=(j,0,j+1,w))


class ImageWidget(WidgetBase):
    '''Only tk supported image formats or supply PhotoImage (pil)
    '''
    def __init__(self, parent, image, use_cache=True, resize=None):
        '''
        image : ImageImage or string
        '''
        super().__init__(parent)
        
        if isinstance(image, ImageImage):
            pass
        else:
            image = common_build_image(ImageImage, image,
                                       use_cache=use_cache)
            
        self.image = image
        if image is not None:
            self.tk = tk.Label(parent.tk, image=self.image.tk)
        else:
            self.tk = tk.Label(parent.tk)
   

    def _resize(self):
        pass

    def set_from_file(self, fn):
        # Tkinter cannot open files on shm (other filesystems)
        # apparently and not JPEGs - using late import
        if fn.endswith('jpg') or fn.startswith('/dev/shm'):
            from PIL import ImageTk, Image
            image = Image.open(fn)
            self.tk_photoimage = ImageTk.PhotoImage(image)
            fn = self.tk_photoimage
        try:
            self.tk.configure(image=fn)
        except Exception as e:
            print(e)


class CanvasWidget(WidgetBase):
    '''ImageWidget on steroids, drawable
    '''

    def __init__(self, parent, width, height, bg="white"):
        super().__init__(parent)

        self.tk = tk.Canvas(
                parent.tk,
                width=width, height=height,
                bg=bg,
                )

    def draw_line(self, points, width=1, color="#101010"):
        return self.tk.create_line(
                *points, width=width, fill=color)

    def draw_rectangle(self, points, width=1,
                         color="#101010", fillcolor=""):
        return self.tk.create_rectangle(
                *points, width=width, outline=color, fill=fillcolor)


    def draw_image(self, image, x, y):
        if isinstance(image, ImageImage):
            image = image.tk
        elif isinstance(image, ImageWidget):
            image = image.image.tk
        elif isinstance(image, tk.PhotoImage):
            pass
        elif isinstance(image, tk.BitmapImage):
            pass
        else:
            imtype = type(image)
            raise ValueError(f'Unkown image type: {imtype}')
        return self.tk.create_image(x,y, image=image)
