'''Common classes for all backends
'''

import sys

IMAGE_CACHE = []

def common_build_image(imclass, image, use_cache=True):
    '''Returns the ImageImage

    image : str or None
    '''
    if isinstance(image, str):
        image_fn = image
        if use_cache and image_fn in IMAGE_CACHE:
            image = IMAGE_CACHE[image_fn]
        else:
            image = imclass(image_fn)
    elif image is None:
        image = None
    else:
        imtype = type(image)
        raise TypeError(f"Unfitting image type: {imtype}")

    return image


class Events:
    ButtonPress = 0
    ButtonRelease = 1


class CommonCommonBase:
    pass


class CommonMainBase:
    '''MainWindow
    '''
    def __init__(self):
        self._refresh = None
        self.running = False

        if '--preload_level_2' in sys.argv:
            input()

    def run(self):
        '''Starts the programs main loop.
        '''
        has_l2 = '--preload_level_2' in sys.argv
        has_l3 = '--preload_level_3' in sys.argv

        if has_l3:
            input()

        if (has_l2 or has_l3) and callable(self.refresh):
            self.refresh()
            
        self.running = True


    @property
    def refresh(self):
        return self._refresh

    @refresh.setter
    def refresh(self, command):
        '''The refresh command for prl levels 2 and 3.
        
        Refresh may be needed if the widgets have have become old
        since the creation (for example to update a clock widget
        to right time)
        '''
        if callable(command):
            self._refresh = command
        else:
            type_ = type(command)
            raise ValueError(f'Command has to be callable, not {type_}')


    def parse_geometry(self, string):
        
        #get the dimenstions of teh screen and set the widows format to 4/3
        sw = self.screen_width
        sh = self.screen_height
        ratio = 4/3

        #if we mentionned a size of the window we want, we pick a proportion of the size of the screen
        if string == 'small' or string == 'medium' or string == 'large' or string == 'fill':

            if string == 'small':
                s = 0.3
            elif string == 'medium':
                s = 0.6
            elif string == 'large':
                s = 0.8
            elif string == 'fill':
                s = 1
                ratio = sw/sh #we reset the ratio to the one of the screen as we want the window to fill all of it

            h = int(sh * s) #we compute the height based of the proportion we picked
            if h >= sh - 100: #we check that the window fits within 100 pixels of the full height size (although I don't understand why as it is based on the size of the screen so it will always fit, unless we chose "fill" but then I don't get why changing, maybe it's for the windows' borders?)
                h = sh-100
                ratio *= 1.1
 
            w = int(ratio*h) #we compute the width based on the screen ratio and the height we picked.
            if w > sw: #if it is too large, we set it as the maximum width of the screen
                w = sw
           
            return int(w), int(h), None, None
        else: #if we provided a dimention format based on tk original format (e.g. "1920x1080+X+Y", with X and Y coordinates of the window)
            width, height = string.split('x')
            if '+' in height: #check if user passed a x and y coordinates
                if height.count('+')==2: #if passed correctly, there should be 2 '+' in the string, if not we just take the height and ignore the rest
                    height, x, y = height.split('+')
                    return int(width), int(height), int(x), int(y)
                    
                else:
                    height = height.split('+')[0] #we keep the height
                    return int(width), int(height), None, None
            else:
                return int(width), int(height), None, None
            
        

class CommonWidgetBase:
    
    @property 
    def margins(self):
        return getattr(self, '_margins', (0,0,0,0))

    @margins.setter
    def margins(self, sides):
        length = len(sides)
        if length != 4:
            raise ValueError('Marings need len == 4, {length}')
        self._margins = sides

    def get_root(self):
        parent = self.parent
        while True:
            if isinstance(parent, CommonMainBase):
                return parent
            try:
                parent = parent.parent
            except:
                return None

