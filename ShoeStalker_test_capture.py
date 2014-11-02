#!/usr/bin/env python

"""
October ___, A worked on camera capture things.

October 23, J+C added finding keypoints code. worked with rosbag.

October 24, C - Code runs!! HUZZAH. Doesn't do anything yet. Working on keypoints stuff. See pauls_track_object.py for possible understanding?

October 28, J - learned about implementing color histogram and SIFT.

October 28, A - added capability of reading image from Neato stream. added mouse events function. 
	Added Detect from Paul's code (altered for our use). 

"""
import rospy
import cv2
import numpy as np

from geometry_msgs.msg import Twist, Vector3
from matplotlib import pyplot as plt
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError

class ShoeStalker:
	SELECTING_NEW_IMG = 0

	def __init__(self,descriptor):

		self.detector = cv2.FeatureDetector_create(descriptor)
		self.extractor = cv2.DescriptorExtractor_create(descriptor)
		self.matcher = cv2.BFMatcher()
		self.new_img = None
		#cv2.imread('./shoefront/frame0000.jpg')
		self.new_region = None
		self.last_detection = None

		self.corner_threshold = 0.0
		self.ratio_threshold = 1.0

		self.state = ShoeStalker.SELECTING_NEW_IMG

		try:
			#for image capture 
			self.camera_listener = rospy.Subscriber("camera/image_raw",Image, self.capture)
			self.bridge = CvBridge()
			#make image something useful
		except AttributeError:
			print "ERROR!"
			pass	

		# try:
		# 	#self.bridge = CvBridge()
		# except NameError:
		# 	pass
		
		self.new_img = None
		self.new_region = None
		self.last_detection = None

		print "initiated!"

	def capture(self,msg):
		# IMAGE FROM NEATO 
		#useful link for image types http://wiki.ros.org/cv_bridge/Tutorials/ConvertingBetweenROSImagesAndOpenCVImagesPython
		cv_Shoeimage = self.bridge.imgmsg_to_cv2(msg, "bgr8")
		#Shoeimage = np.asanyarray(cv_Shoeimage)
		self.new_img = cv_Shoeimage
		cv2.imshow("ShoeStream", cv_Shoeimage)
		print "image"

		# # set up the ROI for tracking
		# region = self.new_img[self.new_region[1]:self.new_region[3],self.new_region[0]:self.new_region[2],:]
		# hsv_region =  cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

		# #FOR THE WEBCAM 
		# #take picture of shoe 
		# capture = cv.CaptureFromCAM(0)
		# img = cv.NewFrame(capture)
		# plt.imshow(img, cmap = 'gray', interpolation = 'bicubic') # shows image
		# #save image to specific location
		# cv.SaveImage("captured_shoe",img)
		# #read back image (necessary?)
		# img = cv2.imread('captured_shoe')
		# if cv2.waitKey(1) & 0xFF == ord('q'):
		# 	print 'break'
		# 	#break
		# # When everything done, release the capture
		# cap.release()

	def set_ratio_threshold(self,thresh):
		self.ratio_threshold = thresh

	def set_corner_threshold(self,thresh):
		self.corner_threshold = thresh

	def get_new_keypoints(self):
		#makes new image black and white
		if self.new_img == None:
			return
		print self.new_img
		new_img_bw = cv2.cvtColor(self.new_img,cv2.COLOR_BGR2GRAY)
		#detect keypoints
		keyp = self.detector.detect(new_img_bw)
		#compare keypoints
		keyp = [point
			  for point in keyp if (point.response > self.corner_threshold and
							   self.new_region[0] <= point.point[0] < self.new_region[2] and
							   self.new_region[1] <= point.point[1] < self.new_region[3])]
		dc, describe = self.extractor.compute(new_img_bw,keyp)
		#remap keypoints so relative to new region
		for point in keyp:
			point.point = (point.point[0] - self.new_region[0],point.point[1] - self.new_region[1])
		#reassign keypoints and descriptors
		self.new_keypoints = keyp
		self.new_descriptors = describe

	def detect(self, im):
		print 'detect'

		#Pauls Code - went through it and changed it to fit ours. will probably need further alterations
		img_bw = cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
		training_keypoints = self.detector.detect(img_bw)

		desc, trainig_descriptors = self.estractor.compute(img_bw, training_keypoints)
		#finds the k best matches for each descriptor from a query set. (http://docs.opencv.org/modules/features2d/doc/common_interfaces_of_descriptor_matchers.html)
		matches = self.matcher.knnMatch(self.new_descriptors, training_descriptors, k=2)
		good_matches = []
		for m,n in matches: 
			#makes sure distance to closest match is sufficiently better than to 2nd closest
			if (m.distance < self.ration_threshold*n.distance and
				training_keypoints[m.trainIdx].response >self.corner_threshold):
				good_matches.append((m.queryIdx, m.drainIdx))

		self.matching_new_pts = np.zeros((len(good_matches),2))
		self.matching_training_pts = np.zeros((len(good_matches),2))

		track_im = np.zeros(img_bw.shape)
		for idx in range(len(good_matches)):
			match = good_matches[idx]
			self.matching_new_pts[idx,:] = self.new_keypoints[match[0]].pt
			self.matching_training_pts = training_keypoints[match[1]].pt
			track_im[training_keypoints[match[1]].pt[1], training_keypoints[match[1]].pt[0]] = 1.0

		track_im_visualize = track_im.copy()

		#converting to (x,y,z,h)
		track_region = (self.last_detection[0],self.last_detection[1],self.last_detection[2]-self.last_detection[0],self.last_detection[3]-self.last_detection[1])

		#setup criterial for termination, either 10 iteritation or move at least 1 pt
		#done to plot intermediate results of mean shift
		for max_iter in range(1,10):
			term_crit = ( cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, max_iter, 1 )
			(ret, intermediate_region) = cv2.meanShift(track_im,track_region,term_crit)
			cv2.rectangle(track_im_visualize,(intermediate_region[0],intermediate_region[1]),(intermediate_region[0]+intermediate_region[2],intermediate_region[1]+intermediate_region[3]),max_iter/10.0,2)
		
		self.last_detection = [intermediate_region[0],intermediate_region[1],intermediate_region[0]+intermediate_region[2],intermediate_region[1]+intermediate_region[3]]

		cv2.imshow("track_win", track_im_visualize)

		#compare image of the shoe to shoe database (color histogram/SIFT technique) (this may be very time-consuming)
		#pick shoe by image of shoe with the most keypoints
		#return location of shoes (I think it might be easier to use one location of a shoe)

		xpos = 0
		distance = 0
		return xpos,distance

	def stalk(self): #potentially add distance to shoe if that happens
		print 'stalk'
		#move robot so shoe is in center of image (or will it already be like this?)
		#move towards the shoes

		#xpos,distance = self.detect(self.new_image)

		#if xpos > 0:
			#linear = .5
			#angular = xpos * something depending on what the units of xpos are
			#pub.publish(Twist(linear=Vector3(x=linear),angular=Vector3(z=angular)))
		#else:
			#self.lostshoe()

	def lostshoe(self):
		print 'lost shoe'
		#refind a lost shoe, turn towards location of last view
		#currently just turning

		#linear = 0
		#angular = .8
		#pub.publish(Twist(linear=Vector3(x=linear),angular=Vector3(z=angular)))

	# def run(self):  #doesn't seem to be necessary...
	# 	print 'run'
		# capture = cv2.VideoCapture(0)
		# ret, frame = capture.read()
		# cv2.namedWindow("image")
		# cv2.imshow("image",frame)
		
	def preloaded_reference_image(self):
		"""displays and assigns a preloaded reference image to save time testing code"""
		print 'preloaded reference'
		frame = self.new_img
		cv2.namedWindow('preloaded reference')
		cv2.imshow("preloaded reference",frame)
		cv2.waitKey(0)
		cv2.destroyAllWindows()

	# def publisher(self):
	# 	pub=rospy.Publisher('cmd_vel',Twist,queue_size=10)
	# 	rospy.init_node('ShoeStalker', anonymous = True )
	# 	pub.publish('a')
	# 	rospy.spin()

	def set_corner_threshold_callback(thresh):
		""" Sets the threshold to consider an interest point a corner.  The higher the value
			the more the point must look like a corner to be considered """
		self.set_corner_threshold(thresh/1000.0)

	def set_ratio_threshold_callback(ratio):
		""" Sets the ratio of the nearest to the second nearest neighbor to consider the match a good one """
		self.set_ratio_threshold(ratio/100.0)


	def mouse_event(event,x,y,flag):
		if event == cv2.EVENT_FLAG_LBUTTON:
			if self.state == self.SELECTING_NEW_IMG:
				self.new_img_visualize = frame.copy()
				self.new_img = frame
				self.new_region = None
				self.state = self.SELECTING_REGION_PT_1
			elif self.state == self.SELECTING_REGION_PT_1:
				self.new_region = [x,y,-1,-1]
				cv2.circle(self.new_img_visualize,(x,y),5,(255,0,0),5)
				self.state = self.SELECTING_REGION_PT_2
			else:
				self.new_region[2:] = [x,y]
				self.last_detection = self.new_region
				cv2.circle(self.new_img_visualize,(x,y),5,(255,0,0),5)
				self.state = self.SELECTING_NEW_IMG
				self.get_new_keypoints()		

if __name__ == '__main__':
	
	try:
		rospy.init_node('capture', anonymous=True)
		n = ShoeStalker('SIFT')


		#creating UI window and integrating mouse event 
		cv2.namedWindow('UI')
		cv2.createTrackbar('Corner Threshold', 'UI', 0, 100, n.set_corner_threshold_callback)
		cv2.createTrackbar('Ratio Threshold', 'UI', 100, 100, n.set_ratio_threshold_callback)
		cv2.namedWindow("ShoeStream")
		cv2.setMouseCallback("ShoeStream", n.mouse_event)

		while not(rospy.is_shutdown()):
			cv2.waitKey(50)
			# n.get_new_keypoints()  # had to comment out to get have code run for image capture 11/1
	#	n.publisher()
	except rospy.ROSInterruptException: pass