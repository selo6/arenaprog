'''Generate card-style stimuli on the fly.

Card-stimuli can contain patterns and colors and different cards can be
quickly and efficiently swapped to other cards.

It is well suited for presenting different kind of non-moving
patters and images.

Use somthing else for high-framerate moving stimuli or long videos.
'''
import math
import random

from PIL import Image, ImageDraw

import devjoni.guibase as gb


CARD_WIDTH = 200
CARD_HEIGHT = 200


def _calc_variations(N):
    '''Calculate the pie binary variations
    '''
    
    if N == 4:
        # Alice style variations (rotations eliminated)
        variations = ["0000", "0001", "0011", "1010", "0111", "1111"]
        return variations

    # General case but does not check rotationally 
    # similar variations

    variations = []
    variation = '0'*N
    while True:
        # Advance variation by one and quit when done
        variation = bin(int(variation,2)+1)[2:].zfill(N)
        if len(variation) > N:
            break
        variations.append(variation)
    return variations

def _randomize_rotation(variation):
    # Cut index
    index = random.randint(0, len(variation)-1)
    return variation[index:] + variation [:index]

def _draw_pie(image, x0, y0, x1, y1, variation):
    '''Draw a pie on the Pillow image

    Arguments
    ---------
    image : Image object
        Pillow image
    x0, y1, x1, y1 : int
        Coordinates of the area filled with the pie
    variation : string
        Variation of the pie, for example "0101"
    '''
    ctx = ImageDraw.Draw(image)

    variation = _randomize_rotation(variation)

    opening = 360 / len(variation)
    
    for i_boolean, boolean in enumerate(variation):
        if boolean == '1':
            ctx.pieslice(
                    [(x0,y0),(x1,y1)],
                    i_boolean*opening, (i_boolean+1)*opening,
                    fill=(255,255,255))

    w = x1-x0
    h = y1-y0

    cp = [int(w/2+x0),int(h/2+y0)]
    r = int(min(w/2,h/2))
    ctx.circle(cp,r)


def create_centraldot_images(r_rel, width=CARD_WIDTH, height=CARD_HEIGHT,
                             seed=None,nb_card=10):
    '''
    r_rel : float
        Radius relative to the smallest image dimension, width or height
    '''

    images = []

    setseed(seed)
    
    for i in range(nb_card):
        image = Image.new('RGB', (width, height))
        ctx = ImageDraw.Draw(image)
        
        R = int(r_rel*min(width, height)/2)
        cp = [int((width-R*2)*random.random()+R),
              int((height-R*2)*random.random()+R)]
        
        ctx.circle(cp, R, fill=(255,255,255))
        images.append(image)

    setseed(None)

    return images


def create_onepie_images(N, width=CARD_WIDTH, height=CARD_HEIGHT,
                         seed=None):
    '''Create a image with one pie

    Attributes
    ----------
    N : int
        The amount of slices in the pattern
    '''
    setseed(seed)

    images = []

    for variation in _calc_variations(N):        
        image = Image.new('RGB', (width, height))
        _draw_pie(image, 0, 0, width, height, variation)
        images.append(image)

    setseed(None)

    return images

def create_stripe_image(width=CARD_WIDTH, height=CARD_HEIGHT, seed=None):
    setseed(seed)
    

    image = Image.new('RGB', (width, height))
    ctx = ImageDraw.Draw(image)

    for i in range(0,height,10):
         ctx.line((0,i), (width-1, i))

    setseed(None)

    return [image]

def setseed(state):
    random.seed(state)



def create_multipie_images(N, M, right='1010', width=CARD_WIDTH, height=CARD_HEIGHT, seed=None, nb_card=12):
    '''Create a image with one pie

    Attributes
    ----------
    N : int
        The amount of slices in the pattern
    M : int
        The amount of patterns
    '''
    images = []

    setseed(seed)

    right = right.zfill(M)[0:M]
    
    variations = _calc_variations(N)
    if right in variations:
        variations.remove(right)

    mrot = 360/M
    wpie = min(width, height)/M


    for i in range(nb_card):
        
        right_rot = random.randint(0,M-1)

        image = Image.new('RGB', (width, height))
        
        for irot in range(M):
            cp = [
                    math.cos(math.radians(irot*mrot))*(
                        width/2-wpie)+ width/2,
                    math.sin(math.radians(irot*mrot))*(
                        height/2-wpie) + height/2]

            if irot == right_rot:
                variation = right
            else:
                variation = random.choice(variations)

            _draw_pie(
                    image,
                    cp[0]-wpie/2, cp[1]-wpie/2,
                    cp[0]+wpie/2, cp[1]+wpie/2,
                    variation)

        images.append(image)
    
    setseed(None)


    return images


def create_calibcross_images(r_rel, xx, yy, width=CARD_WIDTH, height=CARD_HEIGHT):
    '''
    definition used to create crosses at specific coordinates for the user to click on during the camera/mask calibration.
    xx and yy are the coordinate of teh centre of the cross
    '''
    #generate the image
    image = Image.new('RGB', (width, height))
    ctx = ImageDraw.Draw(image)

    #compute the length of the branches of the cross
    rel_length=int(r_rel*min(width, height)/2)

    #compute the coordinates of the line forming the horizontal branches
    hx0=xx-rel_length
    hy0=yy
    hx1=xx+rel_length
    hy1=yy

    #compute the coordinates of the line forming the vertical branches
    vx0=xx
    vy0=yy-rel_length
    vx1=xx
    vy1=yy+rel_length

    #plot the lines to make the cross
    ctx.line((hx0,hy0,hx1,hy1), fill=(255,255,255))
    ctx.line((vx0,vy0,vx1,vy1), fill=(255,255,255))

    return image


class CardWidget(gb.FrameWidget):
    '''A stimulus

    Load method is pretty slow, Hide and Show fast.
    '''
    def __init__(self, parent, width=CARD_WIDTH, height=CARD_HEIGHT):
        super().__init__(parent)
        
        image = gb.ImageImage(None, width, height)
        self.widget = gb.ImageWidget(self, image)
        self.widget.grid()

        self.set(bg="black")
        self.widget.set(bg="black")


    def load(self, image):
        '''Load image

        image : Image
            Pillow image object
        '''
        self.widget.image.set_from_rgb(image)


class CardStimWidget(gb.FrameWidget):
    '''Generate different simulus cards

    Attributes
    ----------
    next_card_callback : None or callable
        Function or method to be called every time the card is changed
    '''
    def __init__(self, parent, width=CARD_WIDTH, height=CARD_HEIGHT,
                 make_nextbutton=True):
        super().__init__(parent)


        self.card_methods = [
            self.create_centraldot_cards,
            self.create_onepie_cards,
            self.create_multipie_cards,
            #self.create_stripe_cards,
            ]


        self.width = width
        self.height = height

        self.cards = []
        self.current_card = None
        
        if make_nextbutton:
            self.b_next = gb.ButtonWidget(self, 'Next', command=self.next_card)
            self.b_next.grid(row=0, column=0)
        
        self.set(bg="black")

        self.next_card_callback = None

    def next_card(self, do_callback=True):
        if not self.cards:
            return

        if self.current_card is None:
            index = 0
        else:
            index = self.cards.index(self.current_card)
            try:
                self.current_card.grid_remove()
            except Exception as e:
                print(e)
            index+=1

        if index >= len(self.cards):
            index = 0
       
        self.current_card = self.cards[index]
        self.current_card.grid(row=1, column=0)

        if do_callback and callable(self.next_card_callback):
            self.next_card_callback()

    def create_card(self, image):
        '''Manually create and add a card from the given image

        image : Image object
            Pillow image
        '''
        h = image.height
        w = image.width

        converted = []
        _converted = list(image.getdata())
        for i_row in range(image.height):
            row = _converted[i_row*w:(i_row+1)*w]
            converted.append(row)

        card = CardWidget(self, self.width, self.height)
        card.load(converted)

        self.cards.append(card)

    def clear_cards(self):
        self.cards = []

    
    def create_centraldot_cards(self, seed=None,nb_card=10):
        '''Create cards that show one central dot
        '''
        self.clear_cards()

        images = create_centraldot_images(
                r_rel=0.1, width=self.width, height=self.height,
                seed=seed, nb_card=nb_card
                )

        for image in images:
            self.create_card(image)
        self.current_card = None


    def create_onepie_cards(self, N=4, seed=None, nb_card=10):
        '''Change to onepie cards
        '''
        self.clear_cards()

        images = create_onepie_images(
                N, width=self.width, height=self.height,
                seed=seed,nb_card=nb_card)
        for image in images:
            self.create_card(image)
        self.current_card = None


    def create_multipie_cards(self, N=4, M=4, seed=None, nb_card=10):

        self.clear_cards()

        images = create_multipie_images(
                N, M, width=self.width, height=self.height,
                seed=seed,nb_card=nb_card)
        for image in images:
            self.create_card(image)

        self.current_card = None


    def create_stripe_cards(self, seed=None, nb_card=10):
        self.clear_cards()

        images = create_stripe_images(self.width,self.height,seed)
        for image in images:
            self.create_card(image)

        self.current_card = None

    #create the definition to generate the card of the calibration crosses
    def create_calibcross_cards(self,relat_size=0.1, XX=100, YY=100):
        '''to create calibration cards
        relat_size is to change the size relative to the size of the card (between 0 and 1)
        XX and YY are the coordinate of the centre of the cross'''

        self.clear_cards()

        calib_image = create_calibcross_images(r_rel=relat_size, xx=XX, yy=YY, width=self.width, height=self.height)
        
        self.create_card(calib_image)

        self.current_card = None

def main():
    
    window = gb.MainWindow()
    window.title = f'Test stimulus'
    
    view = CardStimWidget(window)
    view.grid()

    view.create_multipie_cards()

    window.run()

if __name__ == "__main__":
    main()
