import cv2
# Import the video capturing function
from .video_capture_openCV import VideoCaptureAsync
import time

def record_video_cv2(duration=None, vid_w = 1280, vid_h = 800, preview_rate=10,save_path='video.avi',save_codec='DIVX'):
    '''Used to record videos using the opencv package.
    Optional parameters:
    duration --> (in seconds) if user wants to stop the recording after a given duration.
    vid_w --> recording width in pixels.
    vid_h --> recording height in pixels.
    preview_rate --> rate of frames from the recording that will also be displayed to the user. 
                    By default every 10 frames will be displayed. A lower number will increase the strain on the system and may slowe down the recording rate.
    save_path --> character string of the full path of the video to be saved (folder path + video name + extention, usually .avi)
    save_codec --> codec to use to save the video. 'XVID' and 'DIVX' works. Check to see what else is available. Please change the file expension accordingly.'''
    #clode the opencv windows that were already open (like if we made a previsualisation one) before to start recording
    cv2.destroyAllWindows()

    #Intiate Video Capture object
    capture = VideoCaptureAsync(src=0, width=vid_w, height=vid_h)
    #Intiate codec for Video recording object
    fourcc = cv2.VideoWriter_fourcc(*save_codec)
    
    #start video capture
    capture.start()

    #get the time when the recording starts
    time_start = time.time()

    #if the user mentionned a maximum duration we compute the end time, otherwise we give one in 10 years (an crazy far so we don't have to worry about the recording stopping on its own)
    if duration:
        time_end = time.time() + duration
    else:
        time_end = time.time() + 3.154e+8

    frames = 0
    #Create array to hold frames from capture
    images = []
    # Capture for duration defined by variable 'duration'
    while cap.isOpened() or time.time() <= time_end:
        ret, new_frame = capture.read()
        frames += 1
        images.append(new_frame)
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
            frame = cv2.resize(new_frame,(1280,800))
            frame = cv2.flip(frame,180)
            cv2.imshow('frame', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): #press q to stop the process
            break
        if cv2.getWindowProperty('preview',cv2.WND_PROP_VISIBLE) < 1: #or check that the display window has been manually closed by the user
            break
    capture.stop()
    cv2.destroyAllWindows()
    # The fps variable which counts the number of frames and divides it by 
    # the duration gives the frames per second which is used to record the video later.
    time_total=time.time() - time_start
    fps = frames/time_total
    print(frames)
    print(fps)
    print(len(images)) 
    # The following line initiates the video object and video file named 'video.avi' 
    # of width and height declared at the beginning.
    out = cv2.VideoWriter(save_path, fourcc, fps, (vid_w,vid_h))
    print("creating video")
    # The loop goes through the array of images and writes each image to the video file
    for i in range(len(images)):
        out.write(images[i])
    images = []
    print("Done")


def preview_video_cv2():

    cv2.namedWindow("preview")
    vc = cv2.VideoCapture(0)

    if vc.isOpened(): # try to get the first frame
        rval, frame = vc.read()
    else:
        rval = False

    while rval and vc.isOpened(): 
        cv2.imshow("preview", frame)
        rval, frame = vc.read()
        if cv2.waitKey(1) & 0xFF == ord('q'): #press q to exit
            break
        if cv2.getWindowProperty('preview',cv2.WND_PROP_VISIBLE) < 1: #or check that the display window has been manually closed by the user
            break
        if q_video.pop=="stop":
            break

    cv2.destroyAllWindows()
    vc.release()
