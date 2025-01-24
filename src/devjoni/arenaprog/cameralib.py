''' Cameralib - Camera reading using opencv
'''

import cv2
import multiprocessing

from devjoni.hosguibase.imagefuncs import rgb2hex

def detect_cameras():
    cameras = []
    for i in range(0,5):
        try:
            cam = cv2.VideoCapture(i)
            cameras.append(i)
        except:
            break
    return cameras


class Camera:
    def __init__(self, i_camera):
        self.i_camera = i_camera
        self.cam = cv2.VideoCapture(i_camera)
        self._is_open = False

    def get_frame(self):
        if not self._is_open:
            raise RuntimeError('Camera has not been opened')

        self.cam.grab()
        ret , im = self.cam.retrieve()
        #self.cam.release()
        im = cv2.resize(im, (200,200))
        a = rgb2hex(im, N_jobs=0)
        return im


    def open(self):
        self.cam.open(self.i_camera)
        self._is_open = True

    def close(self):
        self.cam.release()
        self._is_open = False

    def is_open(self):
        return self._is_open

class MultiprocessCamera:
    '''Start the camera in its own process
    '''

    def __init__(self, i_camera):
        self.i_camera = i_camera
        self.p = None

    def _run(self, q1, q2, i_camera):

        camera = Camera(i_camera)
        camera.open()

        while True:

            im = camera.get_frame()
            q1.put(im)

            if not q2.empty():
                camera.close()
                return


    def get_frame(self):
        if self.p is None:
            raise RuntimeError('Camera has not been opened')

        while True:
            if not self.q1.empty():
                break
        
        while True:
            im = self.q1.get()
            if self.q1.empty():
                break

        return im

    def open(self):
        q1 = multiprocessing.Queue()
        q2 = multiprocessing.Queue()
        self.p = multiprocessing.Process(target=self._run, args=[q1,q2, self.i_camera])
        self.q1 = q1
        self.q2 = q2
        self.p.start()


    def close(self):
        if self.p is None:
            return

        self.q2.put('')
        while True:
            try:
                self.p.join(1)
                break
            except:
                print('join failed')
            print(f'Waiting to join')
        self.p = None


    def is_open(self):
        return not (self.p is None)



