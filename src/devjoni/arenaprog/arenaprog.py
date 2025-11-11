'''Arena GUI program
'''

import sys
import atexit
import platform
import random
import os
import numpy as np
import statistics

import devjoni.guibase as gb
from devjoni.hosguibase.video import VideoWidget

from .arenalib import Arena
from .cardstimgen import CardStimWidget

import cv2

#import an opensource package that detects cameras
from cv2_enumerate_cameras import enumerate_cameras

# Import the video capturing function
from .video_capture_openCV import VideoCaptureAsync

#get the module to run multiprocessing
#from multiprocessing import Process
import threading
import multiprocessing
from queue import Queue, Empty
from collections import deque

import time

from skimage.metrics import structural_similarity

from .version import __version__

IMAGE_UPDATE_INTERVAL = 10 # ms


def run_video_preview(camera_index, q_video):
    """A definition that will be used to display the camera images as preview (not recording, just displaying).
    Please turn off before starting the recording"""

    cv2.namedWindow("preview")
    vc = cv2.VideoCapture(camera_index)
    if vc.isOpened():
        rval, frame = vc.read()
    else:
        rval = False

    while rval and vc.isOpened():
        cv2.imshow("preview", frame)
        rval, frame = vc.read()
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        if cv2.getWindowProperty('preview', cv2.WND_PROP_VISIBLE) < 1:
            break
        try:
            msg = q_video.get_nowait()
            if msg == "stop":
                break
        except Empty:
            pass

    cv2.destroyAllWindows()
    vc.release()


def create_calib_mask(camera_index=None, image=None, calib_background=None):
    '''Definition to create a mask based on the automatic detection of the location of the stimuli. 
    The mask is used for the movement detector to detect when the fly passes over the stimulus.
    Depening on the method chosen, get a mask to place over the movement detection images 
    for the detection of the flie entering the stimulus location or use provided.'''

    #if no image provided, we get our own from the camera
    if image is None:
        #close the opencv windows that were already open (like if we made a previsualisation one) before to start capturing an image
        cv2.destroyAllWindows()

        #open a new video window and get the input from the camera
        #cv2.namedWindow("calib")
        vc = cv2.VideoCapture(camera_index) 

        if vc.isOpened(): # try to get the first frame
            rval, stimu_for_mask_image = vc.read()
        else:
            rval = False

        #if we've got an image, make it the same dimension and rotation than the recording one, make it gray and show it
        if rval and vc.isOpened():
            stimu_for_mask_image_temp=cv2.resize(stimu_for_mask_image,(1280,800))
            stimu_for_mask_image_temp2 = cv2.flip(stimu_for_mask_image_temp,180)
            stimu_for_mask_image_GRAY=cv2.cvtColor(stimu_for_mask_image_temp2, cv2.COLOR_BGR2GRAY)
            
            #cv2.imshow("masking image", stimu_for_mask_image_GRAY)
    else:
        #load the image passed
        stimu_for_mask_image=image

        #make it gray (should not need to resize or flip as it comes directly from the recording)
        stimu_for_mask_image_GRAY=cv2.cvtColor(stimu_for_mask_image, cv2.COLOR_BGR2GRAY)
    
    #check if the background image was not given
    if calib_background is None:
        print("Calibration not done")
    else:
        auto_calib_image_GRAY=calib_background


    # --- Absolute difference with background ---
    diff = cv2.absdiff(auto_calib_image_GRAY, stimu_for_mask_image_GRAY)

    # --- Threshold to extract changed pixels ---
    _, mask = cv2.threshold(diff, 100, 255, cv2.THRESH_BINARY)

    # --- Clean noise ---
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)   # remove specks
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)  # close small gaps

    # --- Optional: keep only large enough regions ---
    # useful if projector or camera adds random flicker
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask_clean = np.zeros_like(mask)
    for c in contours:
        if cv2.contourArea(c) > 100:  # keep only "real" stimuli
            cv2.drawContours(mask_clean, [c], -1, 255, -1)

    #cv2.imshow("calib_mask", mask_clean)
    #print("Mask regions:", len(contours))

    #let the user know that the process is done
    print("Mask created")

    return mask_clean


def movement_detect(masking=None, q_video=None, mov_detec_q=None,stop_mov_detec_q=None,next_loop_q=None,time_limit=1,sensitivity=3,auto_reward="n"):
    """function to apply a mask and detect the presence of a new object (e.g. a fly) in images sent from the recording loop, based on changes in gray levels.
    A masking needs to be given based on the create_calib_mask definition.
    It also needs a queue to communicate with the other processes (q_video) and one to receive the images to analyse (mov_detec_q)."""

    #set a switch to know when it is a new detection and that we need to take the time
    frame_detect_switch=0

    #create a list that contains a fixed maximum number of elements, and that removes the first one if it is appended after its full
    gray_list = deque(maxlen=300)

    while(True):

        try:
            analyse_frame=mov_detec_q.get_nowait() #check if there is a frame available in the queue
            gray = cv2.cvtColor(analyse_frame, cv2.COLOR_BGR2GRAY) #convert image to grey levels
            
            if masking is None:
                print("Please generate a mask first") 
                break

            # Compute mean intensity inside the masked region and check how it changed compared to the previous frames. (previous version was directly checking only with the immediate previous frame which did not allow for waiting that the change stays over multiple frames before triggering reward, so the new version below is better)
            roi_mean = cv2.mean(gray, mask=masking)[0] #compute the grey level in the area not masked
            gray_list.append(roi_mean) #add the current level of gray to the list (in the limit of 300 (see above) with the removal of the first value if there is more than 300 already)
            med_gray=statistics.median(gray_list) #compute the median of the gray levels of the previous frames
            gray_diff_result = abs(roi_mean - med_gray) #compute the difference of the mean levels of grey between this frame and the median of the previous ones
            #print(gray_diff_result) #print the difference (we can set a threshold here, instead to trigger an action)
            
            #to show the image with the mask
            #masked_frame = cv2.bitwise_and(gray, gray, mask=masking)
            #cv2.imshow("Masked Frame", masked_frame)

            if gray_diff_result>sensitivity: #if the difference between the two frames reach a threshold, we send the signal to stop the recording
                
                #if this is the first frame with a detection, we catch the time to use later to compute how long the detection lasts
                if frame_detect_switch==0:

                    moment_detect=time.time() #grab the time
                    frame_detect_switch+=1 #switch to 1 to indicate that there is a detection in progress
                    #print("switch ON")
                if frame_detect_switch==1:
                    print(f"Detection running for {time.time() - moment_detect:.2f}s")
                    diff_time=(time.time() - moment_detect) #compute the duration of the change

                    if diff_time>time_limit: #if it is not the first frame, then we check how long the detection lasted and if it is over the limit indicated. If so, we trigger the reward.

                        if auto_reward=="y": #if auto reward option is activated
                            next_loop_q.put("reward") #send the signal to trigger the reward
                            time.sleep(1) #wait 1 second

                        q_video.put("stop") #send the signal to stop the recording

                        #after doing things we need, we close the camera windows and stop the loop
                        #cv2.destroyAllWindows()
                        break   

            else: #if there is no detection in the currect frame set (or reset) the switch to 0
                #set the switch to 0
                frame_detect_switch=0
                #print("switch OFF")

        #except Exception as e: print(e)
        except: #if the queue was empty, pass
            pass
            #print("no frame yet")
            

        #to stop the loop, user can push the q key
        if (cv2.waitKey(1) & 0xFF == ord('q')):
            break

        # Or check if stop was requested by clicking the stop button
        try:
            msg_mov = stop_mov_detec_q.get_nowait()
            if msg_mov == "stop":
                break
        except Empty:
            pass


def record_video_cv2(camera=None,duration=0, vid_w = 1280, vid_h = 800, preview_rate=10, save_path=None, working_folder=os.getcwd(), name_of_video="Video.avi", indiv_name="Fly1", trial_number=None, save_codec='XVID', full_exp='n', auto_detection='n',mov_detec_q=None,stop_mov_detec_q=None,next_card_q=None,next_loop_q=None,q_video=None):
    '''Used to record videos using the opencv package.
    Optional parameters:
    duration --> (in seconds) if user wants to stop the recording after a given duration. If 0, the recording needs to be stopped manually.
    vid_w --> recording width in pixels.
    vid_h --> recording height in pixels.
    preview_rate --> rate of frames from the recording that will also be displayed to the user. 
                    By default every 10 frames will be displayed. A lower number will increase the strain on the system and may slowe down the recording rate.
    save_path --> character string of the full path of the video to be saved (folder path + video name + extention, usually .avi)
    working_folder --> used if the full path is not given, to create a path from information given in the gui
    save_codec --> codec to use to save the video. 'XVID' and 'DIVX' works. Check to see what else is available. Please change the file expension accordingly.
    It needs several queues to communicate with the various processes around the recording:
    mov_detec_q --> to pass images to the movement detector process
    stop_mov_detec_q --> used to send a stop message to the movement detector if teh recording process is terminated
    next_card_q --> in the case of automatising the full experiment it is used to trigger the display of stimuli
    next_loop_q --> in the case of automatising the full experiment it is used to signal that the recording of the trial is done and we can move to teh next one
    q_video --> used to send stop signals from the gui process to the recording and preview process'''
    
    
    # If no path was provided, get it from the widget
    if save_path is None:
        
        #if the trial information is available, we use it, otherwise we do not have trial mentioned in file name
        if trial_number is None:
            trial_info="_"
        else:
            trial_info="_trial" + str(trial_number) + "_"
        
        #assemble the video file name
        video_file=str(indiv_name) + trial_info + name_of_video
        
        #check if the folder path exist and if not create it
        if not os.path.exists(os.path.join(working_folder, indiv_name)):
            os.makedirs(os.path.join(working_folder, indiv_name))
        
        #assemble the full path of the video file
        save_path = os.path.join(working_folder, indiv_name, video_file)
        print(save_path)

    
    #close the opencv windows that were already open (like if we made a previsualisation one) before to start recording
    cv2.destroyAllWindows()

    #clear the queue of images for movement detection
    if auto_detection=="y":
        while not mov_detec_q.empty():
            mov_detec_q.get_nowait()

    #Intiate Video Capture object
    capture = VideoCaptureAsync(src=camera, width=vid_w, height=vid_h)
    #capture = cv2.VideoCapture(camera)
    

    #Intiate codec for Video recording object
    ext = os.path.splitext(save_path)[1].lower()
    if ext == ".avi":
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
    elif ext == ".mp4":
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    else:
        save_path += ".avi"
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
    
    #start video capture
    capture.start()

    """ while not capture.isOpened():
        print("waiting for capture to start") """
    
    #start the writer (the saved video will play at 20fps, the real duration of the video will be saved in a text file)
    out = cv2.VideoWriter(save_path, fourcc, 20, (vid_w,vid_h))

    #get the time when the recording starts
    time_start = time.time()

    #if the user mentionned a maximum duration we compute the end time, otherwise we give one in 10 years (an crazy far so we don't have to worry about the recording stopping on its own)
    if duration!=0:
        time_end = time.time() + duration
    else:
        time_end = time.time() + 3.154e+8

    frames = 0

    #Create array to hold frames from capture
    #images = []

    #if this recording is part of an automtised full experiment process, send the signal to display (change) the stimulus
    if full_exp=="y":
        next_card_q.put("GO!")

    # Capture for duration defined by variable 'duration'
    while time.time() <= time_end:
        ret, new_frame = capture.read()
        frame = cv2.resize(new_frame,(1280,800))
        frame = cv2.flip(frame,180)
        #images.append(new_frame)
        frames += 1
        # Create a full screen video display. Comment the following 2 lines if you have a specific dimension 
        # of display window in mind and don't mind the window title bar.
        #cv2.namedWindow('image',cv2.WND_PROP_FULLSCREEN)
        #cv2.setWindowProperty('image', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        # Here only every 10th frame is shown on the display. Change the preview_rate to a value suitable to the project by passing the value in the function. 
        # The higher the number, the more processing required and the slower it becomes
        if frames ==0 or frames%preview_rate == 0:
            # This project used a Pitft screen and needed to be displayed in fullscreen. 
            # The larger the frame, higher the processing and slower the program.
            # Uncomment the following line if you have a specific display window in mind. 
            #frame = cv2.resize(new_frame,(1280,800))
            #frame = cv2.flip(frame,180)
            #if the autodetection is wanted send frames to the process for analyses
            if auto_detection=="y":
                mov_detec_q.put(frame) #put the frame in the queue for movement detection analysis
            cv2.imshow('frame', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): #press q to stop the process
            break
        #or check that the display window has been manually closed by the user
        if frames>20 and cv2.getWindowProperty('frame',cv2.WND_PROP_VISIBLE) < 1: #we added a frame delay because the window takes time to appear and thus this line stops the loop after one frame (even if we put frames>1 it is not enough)
            break
        # Or check if stop was requested by clicking the stop button
        try:
            msg = q_video.get_nowait()
            if msg == "stop":
                break
        except Empty:
            pass
    capture.stop()
    #capture.release()
    cv2.destroyAllWindows()
    # The fps variable which counts the number of frames and divides it by 
    # the duration gives the frames per second which is used to record the video later.
    time_total=time.time() - time_start
    fps = round(frames/time_total,2)

    #pass a stop signal to the movement detector loop, through its dedicated queue
    stop_mov_detec_q.put("stop")

    print(frames)
    #print(len(images)) 
    print(time_total)
    print(fps)
    # The following line initiates the video object and video file named 'video.avi' 
    # of width and height declared at the beginning.
    """ out = cv2.VideoWriter(save_path, fourcc, fps, (vid_w,vid_h))
    print("creating video")
    # The loop goes through the array of images and writes each image to the video file
    for img in images:
        if img.shape[1] != vid_w or img.shape[0] != vid_h: #if the image captured is not matching the one passed to the video writer, make it match. 
            img = cv2.resize(img, (vid_w, vid_h))
        out.write(img)
    images = [] """

    #save the recording informations in a text file
    with open(str(save_path)+'.txt', 'w') as f:
        f.write("Number of frames: " + str(frames))
        f.write('\n')
        f.write("Fps: " + str(fps))
        f.write('\n')
        f.write("Duration (s): " + str(time_total))

    print("Done")

    if full_exp=="y":
        next_loop_q.put("GO!")


class MovementView(gb.FrameWidget):
    '''Control the arena lift up and down
    '''

    def __init__(self, parent, arena):
        super().__init__(parent)

        self.arena = arena

        self.pos = gb.TextWidget(self, '')
        self.pos.set(text=f'{self.arena.pos}')
        self.pos.grid(row=0, column=0)

        self.move_buttons = []

        for i, N in enumerate([10,3,1,-1,-3,-10]):
            b = gb.ButtonWidget(
                    self, f'Move {N}',
                    lambda N=N: self.move(N)
                    )
            b.grid(row=i+1, column=0)
            self.move_buttons.append(b)

        align = gb.ButtonWidget(self, 'End-align', self.do_align)
        align.grid(row=i+2, column=0)
        

    def move(self, N_steps):
        self.arena.move_platform(N_steps)
        self.pos.set(text=f'{self.arena.pos} ')

    def do_align(self):
        self.arena.step_end_align()
        self.pos.set(text=f'{self.arena.pos}')


class LightView(gb.FrameWidget):
    '''Control the arena lights
    '''
    def __init__(self, parent, arena):
        super().__init__(parent)

        self.arena = arena
        
        self.led_buttons = []
        for i_led in range(self.arena.get_N_leds()):
            b = gb.ButtonWidget(
                    self, f'LED {i_led+1}',
                    command=lambda i=i_led: self.toggle(i))
            b.grid(row=i_led, column=0)
            self.led_buttons.append(b)
    
        self.reward_button = gb.ButtonWidget(
                self, f'Reward 1s', command=self.do_reward)
        self.reward_button.grid(row=i_led+1,column=0)

    def toggle(self, i_led):
        state = self.arena.get_led(i_led)
        state = not state

        self.arena.set_led(i_led, state)

        if state:
            self.led_buttons[i_led].set(bg='green')
        else:
            self.led_buttons[i_led].set(bg='gray')

    def do_reward(self, repeat=True):
        for i_led in range(4):
            self.toggle(i_led)
        if repeat:
            self.after(1000, lambda : self.do_reward(False))
            self.parent.parent.stop_clock()


class StimView(gb.FrameWidget):
    '''Control the stimulus presentation
    '''
    def __init__(self, parent):

        super().__init__(parent)

        self.nb_trials_text = gb.TextWidget(self, 'Number of trials:')
        self.nb_trials_text.grid(row=0, column=0, sticky='WE')

        self.nb_trials = gb.EntryWidget(self)
        self.nb_trials.set_input('20')
        self.nb_trials.grid(row=0,column=1)

        self.b_open = gb.ButtonWidget(
                self, 'Open in window',
                command=self.open_window)
        self.b_open.grid(row=1, column=0)

        self.b_change = gb.ButtonWidget(
                self, 'Change type',
                command=self.change_type)
        self.b_change.grid(row=1, column=1)

        self.b_generate = gb.ButtonWidget(
                self, 'Generate cards',
                command=self.generate_cards)
        self.b_generate.grid(row=2, column=0)
        
        self.preview = CardStimWidget(self, 100, 100)
        self.preview.grid(row=2, column=1)
        self.preview.next_card_callback = self.next_card_callback


        self.view = None

        self.active_type = 0


    def generate_cards(self,number_trials=None):

        # If the number of desired trials was provided, get it from the widget
        if number_trials is None:
            try:
                number_trials = int(self.nb_trials.get_input().strip())
            except (ValueError, AttributeError):
                number_trials = 12  # fallback if input empty or invalid

        #in case a the chronometer is already running, we stop it
        self.parent.stop_clock()

        #when we generate a new type of stimulus, we remove the old type that was open (otherwise it stays on behind the new one). 
        if self.preview.current_card or self.view[1].current_card:
            try:
                self.preview.current_card.grid_remove()
            except:
                pass

            try:
                self.view[1].current_card.grid_remove()
            except:
                pass

        seed = random.random()

        self.preview.card_methods[self.active_type](seed=seed,nb_card=number_trials)
        #self.preview.next_card(do_callback=False) #muted as we want to be able to do the heavy lifting of generating cards long before to display the first one
    
        if self.view:
            self.view[1].card_methods[self.active_type](seed=seed,nb_card=number_trials)
            #self.view[1].next_card(do_callback=False) #muted as we want to be able to do the heavy lifting of generating cards long before to display the first one
        
        #start the chronometer
        self.parent.start_clock()


    #definition to create place the calibration display in the opened stimulus window
    def generate_calib(self,relat_size=0.1, XX=100, YY=100):

        #when we generate a new type of stimulus, we remove the old type that was open (otherwise it stays on behind the new one). 
        if self.preview.current_card or self.view[1].current_card:
            try:
                self.preview.current_card.grid_remove()
            except:
                pass

            try:
                self.view[1].current_card.grid_remove()
            except:
                pass

    
        if self.view:
            self.view[1].create_calibcross_cards(relat_size=relat_size, XX=XX, YY=YY)
            self.view[1].next_card(do_callback=False)
        
    
    def save_card(self):
        pass


    def change_type(self):
        i = self.active_type
        i+=1
        N = len(self.preview.card_methods)

        if i>=N:
            i = 0

        self.active_type = i
        self.b_change.set(text=f"Change type ({i+1}/{N})")


    def open_window(self):
        
        if self.view is not None:
            toplevel, view = self.view
            view.destroy()
            toplevel.destroy()
            self.preview.next_card_callback = None

        root = self.get_root()
        toplevel = gb.MainWindow(parent=root,fullscreen=False,frameless=True,window_geom="400x400+0+0")
        
        view = CardStimWidget(toplevel, 400, 400, make_nextbutton=False)
        #view.b_next.destroy()
        view.grid()

        self.view = [toplevel, view]

        
     
    def next_card_callback(self):
        if self.view:
            self.view[1].next_card()
        self.parent.start_clock()



class CameraControlView(gb.FrameWidget):
    '''Camera controls like start imaging, recording etc.

    Attributes
    ----------
    camera_view : obj or None
        A CameraView Widget to be controlled
    '''
    def __init__(self, parent, arena, camera_view=None):
        super().__init__(parent)

        self.arena = arena

        self.camera_view = camera_view

        self.play_btn = gb.ButtonWidget(self, text='Play', command=self.play)
        self.play_btn.grid(row=0, column=0)

        self.stop_btn = gb.ButtonWidget(self, text='Stop', command=self.stop)
        self.stop_btn.grid(row=0, column=1)
        
        self.change_btn = gb.ButtonWidget(self, text='Next camera', command=self.next_camera)
        self.change_btn.grid(row=0, column=2)
   
        self.record_btn = gb.ButtonWidget(self, text='Record', command=self.record)
        self.record_btn.grid(row=0, column=3)
        
        self.record_details = gb.TextWidget(
                self, text='')
        self.record_details.grid(row=0, column=4)

        self.nb_trials_text = gb.TextWidget(self, 'Number of trials to generate:')
        self.nb_trials_text.grid(row=1, column=0, sticky='WE')

        self.nb_trials = gb.EntryWidget(self)
        self.nb_trials.set_input('20')
        self.nb_trials.grid(row=1,column=1)

        self.video_path_text = gb.TextWidget(self, 'Video name:')
        self.video_path_text.grid(row=2, column=0, sticky='WE')
        
        self.filename = gb.EntryWidget(self)
        self.filename.set_input('video.avi')
        self.filename.grid(row=2,column=1, columnspan=3)

        self.folder_path_text = gb.TextWidget(self, 'Working folder path:')
        self.folder_path_text.grid(row=3, column=0, sticky='WE')
        
        self.folderpath = gb.EntryWidget(self)
        self.folderpath.set_input('C:/Experiment/')
        self.folderpath.grid(row=3,column=1)

        self.fly_name_text = gb.TextWidget(self, 'Individual name:')
        self.fly_name_text.grid(row=4, column=0, sticky='WE')
        
        self.flyname = gb.EntryWidget(self)
        self.flyname.set_input('Fly1')
        self.flyname.grid(row=4,column=1)

        self.video_fps_text = gb.TextWidget(self, 'Video display rate (1/N):')
        self.video_fps_text.grid(row=5, column=0, sticky='WE')
        
        self.fps = gb.EntryWidget(self)
        self.fps.set_input('10')
        self.fps.grid(row=5,column=1)

        self.auto_detect_text = gb.TextWidget(self, 'Automatic detection (y/n):')
        self.auto_detect_text.grid(row=5, column=0, sticky='WE')

        self.auto_detect = gb.EntryWidget(self)
        self.auto_detect.set_input('y')
        self.auto_detect.grid(row=5,column=1)

        self.sensitivity_text = gb.TextWidget(self, 'Automatic detection sensitivity:')
        self.sensitivity_text.grid(row=6, column=0, sticky='WE')

        self.sensitivity = gb.EntryWidget(self)
        self.sensitivity.set_input('3')
        self.sensitivity.grid(row=6,column=1)

        self.detect_duration_text = gb.TextWidget(self, 'Detection duration (s):')
        self.detect_duration_text.grid(row=7, column=0, sticky='WE')

        self.detect_duration = gb.EntryWidget(self)
        self.detect_duration.set_input('1')
        self.detect_duration.grid(row=7,column=1)

        self.auto_reward_text = gb.TextWidget(self, 'Automatic reward (y/n):')
        self.auto_reward_text.grid(row=8, column=0, sticky='WE')

        self.auto_reward = gb.EntryWidget(self)
        self.auto_reward.set_input('y')
        self.auto_reward.grid(row=8,column=1)

        self.calibration_btn = gb.ButtonWidget(self, text='Manual Calibration', command=self.calibration)
        self.calibration_btn.grid(row=9, column=0)

        self.auto_calibration_btn = gb.ButtonWidget(self, text='Auto Calibration', command=self.auto_calibration)
        self.auto_calibration_btn.grid(row=9, column=1)

        self.create_calib_mask_btn = gb.ButtonWidget(self, text='Create Mask', command=self.run_create_calib_mask)
        self.create_calib_mask_btn.grid(row=9, column=2)

        self.full_experiment_btn = gb.ButtonWidget(self, text='Run Experiment', command=self.run_full_experiment_process)
        self.full_experiment_btn.grid(row=10, column=0, columnspan=3)
        self.full_experiment_btn.set(bg='green')

        self.stop_full_experiment_btn = gb.ButtonWidget(self, text='Stop Experiment', command=self.stop_full_experiment_process)
        self.stop_full_experiment_btn.grid(row=11, column=0, columnspan=3)
        self.stop_full_experiment_btn.set(bg='red')

        #start the queue manager for the multiprocessing
        manager = multiprocessing.Manager()

        #get the list of active camras
        self.camera_list=enumerate_cameras(cv2.CAP_MSMF)

        #set the camera number as the first one
        if len(self.camera_list)<1: #if there are no camera detected, let the user know
            print('No camera detected')
        else: #if there are cameras, select the first one and print its info
            self.camera=0
            print(self.camera_list[self.camera])
        
        #create a queue so we can pass stoping messages to the video preview and recording threads.
        self.q_video = manager.Queue()
        self.stop_mov_detec_q = manager.Queue() #same to stop the movement detector thread

        #create a queue so we can pass images from the cam to the movement detector
        self.mov_detec_q = manager.Queue()

        #create a queue to pass a signal to change the stimulus card at the right moment in the recording process
        self.next_card_q = manager.Queue()

        #create a queue to pass the signal to start the next loop (trial) in the automatic running of the full experiment.
        self.next_loop_q = manager.Queue()

        #create a queue to pass the signal to stop the full experiment (automatic) process.
        self.stop_full_exp_q = manager.Queue()

        #create a list to store the calibration coordinates
        self.calib_coord=[]

        #instenciate the StimView class that is used to generate stimuli (see the class above)
        self.stim = StimView(self.parent.parent)

        #instenciate the LightView class that is used to trigger the reward
        self.reward_lights=LightView(self.parent,self.arena)
    

    def play(self):
        # Clear any leftover stop signals
        while not self.q_video.empty():
            self.q_video.get_nowait()

        self.disable_controls()

        # Start external function in a new process
        thrd_preview = multiprocessing.Process(target=run_video_preview, args=(self.camera, self.q_video),daemon=True)
        thrd_preview.start()
        
    
    def record(self):
        '''function that starts the recording process in a new thread so the main gui stays responsive.'''

        # Clear any leftover stop signals
        while not self.q_video.empty():
            self.q_video.get_nowait()

        #get the video name and the path
        video_name=self.filename.get_input().strip() or None
        folder_path=self.folderpath.get_input().strip() or os.getcwd()

        #get the name of the fly
        individual_name=self.flyname.get_input().strip() or None

        #get the response of the user in the gui about activating the autodetection
        activ_autoD=self.auto_detect.get_input().strip()
        activ_autoR=self.auto_reward.get_input().strip()

        #deactivate the buttons so the user doesn't try to trigger another recording or preview while one is running
        self.disable_controls()
        
        #if the autodetection is wanted, start the process
        if activ_autoD=="y":

            #get the response of the user in the gui about the sensitivity to changes in the movement detector and the duration of changes before triggering the reward
            autoD_sensitivity=float(self.sensitivity.get_input().strip())
            autoD_duration=float(self.detect_duration.get_input().strip())

            thrd_detect = multiprocessing.Process(target=movement_detect,kwargs={"masking":self.mask, "q_video":self.q_video,"mov_detec_q":self.mov_detec_q, "stop_mov_detec_q":self.stop_mov_detec_q,"next_loop_q":self.next_loop_q, "time_limit":autoD_duration, "sensitivity":autoD_sensitivity,"auto_reward":activ_autoR}, daemon=True)
            thrd_detect.start()
        
        #start the recording using a new thread from the cpu so the main GUI stays active, pass the optional arguments to the function
        thrd_record = multiprocessing.Process(target=record_video_cv2,kwargs={"camera":self.camera, "working_folder":folder_path, "name_of_video":video_name, "indiv_name":individual_name,"save_path": None, "save_codec": "DIVX", "auto_detection":activ_autoD, "mov_detec_q":self.mov_detec_q, "stop_mov_detec_q":self.stop_mov_detec_q, "next_card_q":self.next_card_q, "next_loop_q":self.next_loop_q, "q_video":self.q_video}, daemon=True)
        thrd_record.start()

        if activ_autoR=="y":
            thrd_reward = threading.Thread(target=self.check_automatic_reward, daemon=True)
            thrd_reward.start()


    def stop(self):
        '''function to to the recording and/or the preview'''
        #trigger a stop for the while loop in the preview_video_cv2() or the record_video_cv2() functions
        #Send a stop signal to the video thread
        self.q_video.put("stop")

        #reanable the buttons in the gui
        self.enable_controls()


    def check_automatic_reward(self,):
        #wait for the end of the recording to move to the new trial
        while(True):
            # check if signal to trigger the reward or to move to the next trial was sent (when the recording started)
            try:
                msg_next_loop = self.next_loop_q.get_nowait()
                if msg_next_loop == "reward":
                    print("Doing reward") #inform the user that we trigger the reward
                    self.reward_lights.do_reward() #trigger the reward
                    time.sleep(1) #wait 1 second
            except Empty:
                pass


    def stop_full_experiment_process(self):
        '''function to stop the automatic run of the full experiment (full set of trials). Including the recording currently running.'''
        #trigger a stop for the full experiment loop and to stop the recording 
        self.stop_full_exp_q.put("stop")
        self.q_video.put("stop")

        #reanable the buttons in the gui
        self.enable_controls()


    #fuunction to change the camera index when the user press the button
    def next_camera(self):
        self.camera+=1 #we add 1 to the index of camera
        if self.camera>(len(self.camera_list)-1): #if the index becomes bigger than the number of cameras, we loop back to the first one
            self.camera=0
        #print the name of the camera    
        print(self.camera_list[self.camera])


    #create a function to desactivate buttons when running either the preview or the recording or full experiment
    def disable_controls(self):
        self.play_btn.set(state="disabled") #user should not launch another preview
        self.record_btn.set(state="disabled") #user should not launch another recording
        self.change_btn.set(state="disabled") #user should not try to change the camera source when a preview or recording is running
        self.calibration_btn.set(state="disabled") #deactivate the buttons to calibrate
        self.auto_calibration_btn.set(state="disabled")
        self.create_calib_mask_btn.set(state="disabled") #deactivate the mask button
        self.full_experiment_btn.set(state="disabled") #deactivate the run full experiment button

    #create a function to reactivate buttons once the preview or the recording process finished
    def enable_controls(self):
        self.play_btn.set(state="normal") #reactivate the preview button
        self.record_btn.set(state="normal") #reactivate the recording button
        self.change_btn.set(state="normal") #reactivate the changing camera source button
        self.calibration_btn.set(state="normal") #deactivate the buttons to calibrate
        self.auto_calibration_btn.set(state="normal")
        self.create_calib_mask_btn.set(state="normal") #deactivate the mask button
        self.full_experiment_btn.set(state="normal")

    def calibration(self): 
        '''This may be used to obtain the pixel location of points on the camera view to match the coordinate system of the projector and the camera.
        At least three points may be necessary (3 for getAffineTransform or 4 for getPerspectiveTransform).
        This would be used to get the stimulus image and make it a mask over the camera view to detect movement only on the area of the stimulus'''
        
        #set the coordinates for the first calibartion cross
        calib1_X=200
        calib1_Y=100
        
        #store them in a list
        self.calib_display_coords=[calib1_X,calib1_Y]

        #open the stimulus window ("stim" is a call of the StimView class that is used to generate stimuli, see above)
        self.stim.open_window()

        #create the calibration display in the opened window
        self.stim.generate_calib(relat_size=0.2, XX=calib1_X, YY=calib1_Y)

        #force tkinter to wait for the window to be opened and the cross to be drawn (otherwise the video window happens before, the loop waiting for the click starts and the cross is never displayed)
        self.stim.view[0].tk.update_idletasks()
        self.stim.view[0].tk.update()

        #close the opencv windows that were already open (like if we made a previsualisation one) before to start capturing an image
        cv2.destroyAllWindows()

        #open a new video window and get the input from the camera
        cv2.namedWindow("calib")
        vc = cv2.VideoCapture(self.camera) 

        if vc.isOpened(): # try to get the first frame
            rval, calib_1 = vc.read()
        else:
            rval = False

        #if we've got an image, show it
        if rval and vc.isOpened():
            cv2.imshow("calib", calib_1)

        # reset coords so we know when user has clicked
        self.clicked_point = None

        # bind the callback function to window
        cv2.setMouseCallback('calib', self.point_capture)

        # Wait until user clicks and that, thus, clicked_point is not empty
        while self.clicked_point is None:
            if cv2.waitKey(1) & 0xFF == ord('q'): #we also plan for closing the loop with pressing q
                break
        
        # save clicked coords
        if self.clicked_point is not None:
            self.calib_coord.extend(self.clicked_point)
        else:
            print("Calibration not Completed")

        #######
        #second calibration cross

        #set the coordinates for the second calibartion cross
        calib2_X=100
        calib2_Y=200
        
        #store them in a list
        self.calib_display_coords.append(calib2_X)
        self.calib_display_coords.append(calib2_Y)

        #create the calibration display in the opened window
        self.stim.generate_calib(relat_size=0.2, XX=calib2_X, YY=calib2_Y)

        #force tkinter to wait for the window to be opened and the cross to be drawn (otherwise the video window happens before, the loop waiting for the click starts and the cross is never displayed)
        self.stim.view[0].tk.update_idletasks()
        self.stim.view[0].tk.update()

        #capture another image from the camera
        if vc.isOpened(): # try to get the first frame
            rval, calib_2 = vc.read()
        else:
            rval = False

        #if we've got an image, show it
        if rval and vc.isOpened():
            cv2.imshow("calib", calib_2)

        # reset coords so we know when user has clicked
        self.clicked_point = None

        # Wait until user clicks and that, thus, clicked_point is not empty
        while self.clicked_point is None:
            if cv2.waitKey(1) & 0xFF == ord('q'): #we also plan for closing the loop with pressing q
                break
        
        # save clicked coords
        if self.clicked_point is not None:
            self.calib_coord.extend(self.clicked_point)
        else:
            print("Calibration not Completed")


        #######
        #third calibration cross

        #set the coordinates for the third calibartion cross
        calib3_X=200
        calib3_Y=300
        
        #store them in a list
        self.calib_display_coords.append(calib3_X)
        self.calib_display_coords.append(calib3_Y)

        #create the calibration display in the opened window
        self.stim.generate_calib(relat_size=0.2, XX=calib3_X, YY=calib3_Y)

        #force tkinter to wait for the window to be opened and the cross to be drawn (otherwise the video window happens before, the loop waiting for the click starts and the cross is never displayed)
        self.stim.view[0].tk.update_idletasks()
        self.stim.view[0].tk.update()

        #capture another image from the camera
        if vc.isOpened(): # try to get the first frame
            rval, calib_3 = vc.read()
        else:
            rval = False

        #if we've got an image, show it
        if rval and vc.isOpened():
            cv2.imshow("calib", calib_3)

        # reset coords so we know when user has clicked
        self.clicked_point = None

        # Wait until user clicks and that, thus, clicked_point is not empty
        while self.clicked_point is None:
            if cv2.waitKey(1) & 0xFF == ord('q'): #we also plan for closing the loop with pressing q
                break
        
        # save clicked coords
        if self.clicked_point is not None:
            self.calib_coord.extend(self.clicked_point)
        else:
            print("Calibration not Completed")

        #close the camera window
        cv2.destroyAllWindows()

        #close the stimulus display window
        self.stim.view[0].tk.destroy()
        self.stim.view = None #not sure what this line is for

        
    #definition to save the coordinates on the video display where the user have clicked during the calibration
    def point_capture(self,event, x, y, flags,params):
        if event == 1:
            self.clicked_point = (x, y)
    

    def auto_calibration(self):
        '''capture the image of the arena with the stimulus display window open but no stimulus displayed 
        to use as comparison with the images collected once stimuli are displayed to auto detect the location of the stimuli'''

        #open the stimulus window ("stim" is a call of the StimView class that is used to generate stimuli, see above)
        self.stim.open_window()

        #force tkinter to wait for the window to be opened before to move on to take the image from the camera
        self.stim.view[0].tk.update_idletasks()
        self.stim.view[0].tk.update()

        #close the opencv windows that were already open (like if we made a previsualisation one) before to start capturing an image
        cv2.destroyAllWindows()

        #open a new video window and get the input from the camera
        #cv2.namedWindow("auto calibration image")
        vc = cv2.VideoCapture(self.camera) 

        if vc.isOpened(): # try to get the first frame
            rval, auto_calib_image = vc.read()
        else:
            rval = False

        #if we've got an image, make it the same dimension and rotation than the recording one, make it gray and show it
        if rval and vc.isOpened():
            auto_calib_image_temp=cv2.resize(auto_calib_image,(1280,800))
            auto_calib_image_temp2 = cv2.flip(auto_calib_image_temp,180)
            self.auto_calib_image_GRAY=cv2.cvtColor(auto_calib_image_temp2, cv2.COLOR_BGR2GRAY)
            
            #cv2.imshow("auto calibration image", self.auto_calib_image_GRAY)
            

        #close the video capture and the window
        cv2.destroyAllWindows()

        #let the user know calibration is done
        print("Calibration complete")

        return(self.auto_calib_image_GRAY)
    
    def run_create_calib_mask(self):
        self.mask=create_calib_mask(camera_index=self.camera,calib_background=self.auto_calib_image_GRAY)
        #thrd_mask = multiprocessing.Process(target=create_calib_mask, args=, daemon=True)
        #thrd_mask.start()


    def run_full_experiment_process(self):
        #deactivate the buttons so the user doesn't try to trigger another recording or preview while one is running
        self.disable_controls()

        thrd_record = threading.Thread(target=self.full_experiment_process, daemon=True)
        thrd_record.start()


    #make a definition that run the full display and recording process for the number of trials indicated
    def full_experiment_process(self):
        
        #clear the queue of sigal to stop the full experiment
        while not self.stop_full_exp_q.empty():
            self.stop_full_exp_q.get_nowait()

        #get the video name and the path
        video_name=self.filename.get_input().strip() or None
        folder_path=self.folderpath.get_input().strip() or os.getcwd()

        #get the name of the fly
        individual_name=self.flyname.get_input().strip() or None

        #get the number of trials
        nb_trial_to_run=int(self.nb_trials.get_input().strip())
        
        #get calibration done
        self.auto_calibration()

        #open the display window
        self.stim.open_window()

        #generate all the cards for the experiment
        self.stim.generate_cards(number_trials=nb_trial_to_run)

        #get the response of the user in the gui about activating the autodetection and autoreward
        activ_autoD=self.auto_detect.get_input().strip()
        activ_autoR=self.auto_reward.get_input().strip()
        
        #if the autodetection is wanted
        if activ_autoD=="y":
            #get the response of the user in the gui about the sensitivity to changes in the movement detector and the duration of changes before triggering the reward
            autoD_sensitivity=float(self.sensitivity.get_input().strip())
            autoD_duration=float(self.detect_duration.get_input().strip())

        #for each trials
        for i in range(nb_trial_to_run):
        
            #clear the queue of signal to display the next stimulus
            while not self.next_card_q.empty():
                self.next_card_q.get_nowait()

            #clear the queue of signal to move to the next loop
            while not self.next_loop_q.empty():
                self.next_loop_q.get_nowait()

            #reset the filter image to None
            first_stim_image=None
        
            #start the recording using a new thread from the cpu so the main GUI stays active, pass the optional arguments to the function
            thrd_record = multiprocessing.Process(target=record_video_cv2,kwargs={"camera":self.camera, "working_folder":folder_path, "name_of_video":video_name, "indiv_name":individual_name, "trial_number": i, "save_codec": "DIVX","full_exp":"y", "auto_detection":activ_autoD, "mov_detec_q":self.mov_detec_q, "stop_mov_detec_q":self.stop_mov_detec_q, "next_card_q":self.next_card_q, "next_loop_q":self.next_loop_q, "q_video":self.q_video}, daemon=True)
            thrd_record.start()

            #wait for the end of the recording to moove to the new trial
            while(True):
                # check if signal to display the next stimulus was sent (when the recording started)
                try:
                    msg_disp_card = self.next_card_q.get_nowait()
                    if msg_disp_card == "GO!":
                        break
                except Empty:
                    pass

            #display the next stimulus
            self.stim.view[1].next_card(do_callback=False)
            self.stim.preview.next_card(do_callback=False)
            
            #wait for the first image of the recording to generate the filter (need to make sure that the first image is capture shortly after the display of teh stimulus not before)
            while(first_stim_image is None):
                try:
                    #get the first image of the camera (which should have the stimulus displayed, otherwise we may want to put a wait time) to use for creating the filter
                    first_stim_image = self.mov_detec_q.get_nowait()
                except Empty:
                    pass

            #if the autodetection is wanted, start the process
            if activ_autoD=="y":

                #create a new mask for the new stimulus display
                self.mask=create_calib_mask(image=first_stim_image, camera_index=self.camera,calib_background=self.auto_calib_image_GRAY)

                #generate the movement detection process and start
                thrd_detect = multiprocessing.Process(target=movement_detect,kwargs={"masking":self.mask, "q_video":self.q_video,"mov_detec_q":self.mov_detec_q, "stop_mov_detec_q":self.stop_mov_detec_q,"next_loop_q":self.next_loop_q, "time_limit":autoD_duration, "sensitivity":autoD_sensitivity,"auto_reward":activ_autoR}, daemon=True)
                thrd_detect.start()

            #Save the card displayed


            #wait for the end of the recording to move to the new trial
            while(True):
                # check if signal to trigger the reward or to move to the next trial was sent (when the recording started)
                try:
                    msg_next_loop = self.next_loop_q.get_nowait()
                    if msg_next_loop == "GO!":
                        break
                    elif msg_next_loop == "reward":
                        print("Doing reward") #inform the user that we trigger the reward
                        self.reward_lights.do_reward() #trigger the reward
                        time.sleep(1) #wait 1 second
                except Empty:
                    pass
            
            #stop the display of the current stimulus before the display of teh next one
            self.stim.preview.current_card.grid_remove()
            self.stim.view[1].current_card.grid_remove()

            #check if the stop signal for the full experiment was triggered (if so, the signal to stop the recording should also have been sent and we should arrive here). 
            try:
                msg = self.stop_full_exp_q.get_nowait()
                if msg == "stop":
                    break
            except Empty:
                pass
            
            #self.stim.view[1].tk.destroy()

            print("trial done, next trial coming up")

        #close the stimulus display window
        self.stim.view[0].tk.destroy()
        self.stim.view = None #not sure what this line is for
    
        #when all the trials are done or the experiment has been stopped, print a message to inform the user
        print("Experiment ended")






#!!!! not sure if this is still useful, maybe I bypassed it in the class above? !!!!
class CameraView(gb.FrameWidget):
    '''Camera view using the opencv cameralib.
    '''
    def __init__(self, parent):
        super().__init__(parent)

        cams = detect_cameras()
        self.camera = MultiprocessCamera(cams[0])

        
        self.image = gb.ImageImage(None, 200,200)
        self.canvas = gb.ImageWidget(self, self.image)
        self.canvas.grid(0,0, sticky='NSWE')

        self._is_playing = False

        atexit.register(self.stop)

    def play(self):
        if self._is_playing:
            return
        self._is_playing = True
        self.camera.open()
        self.after(IMAGE_UPDATE_INTERVAL, self.tick)
        
    def stop(self):
        self._is_playing = False
        self.camera.close()


    def tick(self):
        if not self.camera.is_open():
            return
        im = self.camera.get_frame()
        if im is not None:
            print(im)
            self.canvas.image.set_from_rgb(im)
        
        if self._is_playing:
            self.after(IMAGE_UPDATE_INTERVAL, self.tick)


    def next_camera(self):
        pass


class FastCameraView(gb.FrameWidget):
    def __init__(self, parent):
        super().__init__(parent)
        
        self.video = VideoWidget(self)
        self.video.grid()
        self.video.relative_size=0.75
        self.video.tcoder.source_type = "camera"

        self.ffmpeg_line = ''

        self.do_record = False
        self.record_fn = 'test'
        self.record_fps = 100

    
        cameras = self.video.tcoder.detect_cameras()
        if cameras:
            self.video.source = cameras[0]


    def play(self):
        if self.do_record:
            self.video.fps = self.record_fps
            self.video.tcoder.set_video_output(
                    self.record_fn+'.mp4',
                    resolution=[1280,800],
                    opts=[
                        '-c:v', 'libx264',
                        '-preset', 'ultrafast',
                        '-crf', '28',
                        ])
            
            # Enforce that the webcam is being read fast
            # Arducam UC-844
            system = platform.system()
            if system == 'Linux':
                opts = ['-f', 'v4l2',# '-framerate', str(100),
                        #'-video_size', '1280x800',
                        '-input_format', 'mjpeg']
            else:
                opts = ['-f', 'dshow', #'-video_size', '1280x800',
                        '-rtbufsize', '200M',
                        #'-framerate', str(100),
                        '-vcodec', 'mjpeg']
            self.video.tcoder.source_opts = opts
        else:
            self.video.fps = 10
            self.video.tcoder.set_video_output(None)
            self.video.tcoder.source_opts = None
        self.video.start()

    def stop(self, stop_record=True):
        if self.do_record and stop_record:
            self.do_record = False
        self.video.stop()
    
    def record(self):
        if self.do_record:
            self.do_record = False
        else:
            self.do_record = True
        self.stop(stop_record=False)
        self.play()
    
    def next_camera(self):
        
        # Always stop recording when changing the camera
        if self.do_record:
            self.do_record=False
            self.stop()

        cameras = self.video.tcoder.detect_cameras()
        if not cameras:
            return
        
        if self.video.source not in cameras:
            camera = cameras[0]
        else:
            index = cameras.index(self.video.source)
            index += 1

            if index >= len(cameras):
                index = 0
            camera = cameras[index]
        
        print(camera)
        self.stop()
        self.video.source = camera
        self.play()


class TotalView(gb.FrameWidget):
    def __init__(self, parent, do_camera=True):
        super().__init__(parent)


        try:
            arena = Arena()
        except:
            arena = Arena(fake_serial=True)
        
        # Camera side

        if do_camera:
            camerabox = gb.FrameWidget(self)
            camerabox.grid(row=1, column=1, rowspan=2)
        
            control = CameraControlView(camerabox,arena)
            control.grid(row=0, column=0, sticky='')

            #camera = FastCameraView(camerabox)
            #camera.grid(row=1, column=0)

            #control.camera_view = camera

        # Motion control side
        


        controlbox = gb.FrameWidget(self)
        controlbox.grid(row=1, column=0)
 
        movement = MovementView(controlbox, arena)
        movement.grid(row=0, column=0)
        
        light = LightView(controlbox, arena)
        light.grid(row=0, column=1)

        # Stimulus
        stim = StimView(self)
        if do_camera:
            stim.grid(row=2, column=0)
        else:
            stim.grid(row=1, column=1)
        self.stim = stim
    
        self.time = 0
        self.clock_running=False
        self.time_widget = gb.TextWidget(self, 'Time (s)')
        self.time_widget.grid(row=0, column=0, sticky='WE')

    def start_clock(self):
        self.time = 0
        if not self.clock_running:
            self.clock_running = True
            self.update_clock()

    def update_clock(self):
        self.time += 0.1
        self.time_widget.set(text=f'{self.time:.2f} seconds')
        if self.clock_running:
            self.after(100, self.update_clock)
        else:
            self.stim.preview.current_card.grid_remove()
            if self.stim.view:
                self.stim.view[1].current_card.grid_remove()
            

    def stop_clock(self):
        self.clock_running = False


def main():

    window = gb.MainWindow()
    window.title = f'Arena Program - v{__version__}'
    

    if '--nocamera' in sys.argv:
        do_camera = False
        window.geometry = 'small'
        
    else:
        do_camera = True


    view = TotalView(window, do_camera=do_camera)
    view.grid()

    window.run()



if __name__ == "__main__":
    main()

    #cProfile.run('main()')
