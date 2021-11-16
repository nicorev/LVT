#Conversion Script for waymo Dataset
import sys
import getopt
import os
import utils
from waymo_open_dataset.utils import frame_utils
from waymo_open_dataset.utils import transform_utils
import tensorflow as tf
from waymo_open_dataset import dataset_pb2 as open_dataset
import numpy as np
import PIL
import io
from pyquaternion import Quaternion


# Name of all the cameras
Name  = {
    0:"UNKNOWN",
    1:'FRONT',
    2:'FRONT_LEFT',
    3:'FRONT_RIGHT',
    4:'SIDE_LEFT',
    5:'SIDE_RIGHT'
  }

Lidar_Name = {
    0:"UNKNOWN",
    1:"TOP",
    2:"FRONT",
    3:"SIDE_LEFT",
    4:"SIDE_RIGHT",
    5:"REAR"
}

def extract_rgb(output_path, waymo_path):

    """Extracts the RGB data from a waymo tfrecord and converts it into our intermediate format
    Args:
        output_path: path to LCT directory
        waymo_path: path to waymo data
    Returns:
        None
        """

    #Extract data from TFRecord File
    dataset = tf.data.TFRecordDataset(waymo_path,'')

    frame_num = 0
    #Loop through each frame
    for data in dataset:
        frame = open_dataset.Frame()
        frame.ParseFromString(bytearray(data.numpy()))
        #At this point have one frame imported as 'frame'

        #For the data that's the same in each frame:
        if(frame_num == 0):
            camera_data_int = {}
            camera_data_ext = {}
            # We get the camera names and their intrinsic data
            frame_dict = frame_utils.convert_frame_to_dict(frame)
            for trinsic_data in frame_dict.keys():

                # If we've gotten this far, that means intrinsic_data holds the intrinsic data (and name) of a camera
                if(trinsic_data[-10:] == "_INTRINSIC"):
                    #At this point, matrix is not actually an intrinsic matrix, however it holds the values we need
                    matrix = frame_dict[trinsic_data].tolist()
                    camera_data_int[trinsic_data[:-10]] = [[matrix[0],0,matrix[2]],[0, matrix[1], matrix[3]],[0,0,1]]

                if(trinsic_data[-10:] == "_EXTRINSIC"):
                    camera_data_ext[trinsic_data[:-10]] = frame_dict[trinsic_data]

            

        # finally, with all that settled, let's create the directory and files:
        for image in frame.images:
            if (frame_num == 0):
                translation, rotation_quats = utils.translation_and_rotation(camera_data_ext[Name[image.name]].tolist())
                utils.create_rgb_sensor_directory(output_path, Name[image.name], translation, rotation_quats,
                camera_data_int[Name[image.name]])
            utils.add_rgb_frame(output_path, Name[image.name], PIL.Image.open(io.BytesIO(image.image)), frame_num)
        frame_num += 1

        
    

#Get command line options
def parse_options():
    waymo_path = ""
    output_path = ""
    custom_path = ""
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hf:o:p:", "help")
    except getopt.GetoptError as err:
        print(err)
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print("required: -f to specify the path to the Waymo file")
            print("required: -o to specify the name of the directory where the LVT format will go. Will be a folder in the current directory")
            print("optional: -p to specify a custom path where the LVT format dataset will go")
            sys.exit(2)
        elif opt == "-f":
            waymo_path = arg
        elif opt == "-o":
            output_path = arg
        elif opt == '-p':
            custom_path = arg
        else:
            sys.exit(2)

    return (waymo_path, output_path, custom_path)

def extract_bounding(frame, frame_num, lct_path):
    origins = []
    sizes = []
    rotations = []
    annotation_names = []
    annotation_dict = {1: "Vehicle", 2: "Pedestrian", 3: "Sign", 4:"Cyclist"}
    confidences = []
    for label in frame.laser_labels:
        origins.append(np.transpose(np.matmul(np.array(frame.pose.transform).reshape((4, 4)), np.array(
            [[label.box.center_x], [label.box.center_y], [label.box.center_z], [1]]))).tolist()[0][:3])
        sizes.append([label.box.width, label.box.length, label.box.height])
        annotation_names.append(annotation_dict[label.type])
        quat = Quaternion(axis=[0.0, 0.0, 1.0], radians=label.box.heading)
        rotations.append(quat.q.tolist())
        confidences.append(100)
    utils.create_frame_bounding_directory(lct_path, frame_num, origins, sizes,rotations,annotation_names,confidences)

#Uses the first frame to initialize 
def setup_lidar(frame, lct_path, translations, rotations):
    calibrations = sorted(frame.context.laser_calibrations, key=lambda c: c.name)
    for c in calibrations:

        sensor = c.name
        #Set up the folder for each sensor
        utils.create_lidar_sensor_directory(lct_path, Lidar_Name[sensor])
        transform_matrix = c.extrinsic.transform
  
        #The transaltion matrices are the same for each frame, so this computation is only run once
        translation, rotation = utils.translation_and_rotation(transform_matrix)
        translations[sensor] = translation
        rotations[sensor] = rotation

#Extracts LiDAR data from one frame and puts it in the lct file system
def extract_lidar(frame, frame_num, lct_path, translations, rotations):
    
    #Extract the pointclouds as a list of points
    range_images, camera_projections,range_image_top_pose = frame_utils.parse_range_image_and_camera_projection(frame)
    point_clouds, cp_points = frame_utils.convert_range_image_to_point_cloud(frame,range_images,camera_projections,range_image_top_pose,0,False)

    #There are 5 pointclouds corresponding to the 5 sensors
    for i in range(len(point_clouds)):
        points = point_clouds[i]
        sensor = i+1
        translation = translations[sensor]
        rotation = rotations[sensor]
        utils.add_lidar_frame(lct_path, Lidar_Name[sensor], frame_num, points, translation, rotation)

def extract_ego(frame, frame_num, lct_path):
    translation, rotation_quats = utils.translation_and_rotation(frame.pose.transform)
    utils.create_ego_directory(lct_path, frame_num, translation, rotation_quats)

if __name__ == "__main__":
    (waymo_path, output_path, custom_path) = parse_options()

    #Check if path specified is a Waymo dataset file
    if os.path.splitext(waymo_path)[1] != ".tfrecord":
        print("The file specified is not a tfrecord")
        sys.exit(2)

    path = os.getcwd()
    if len(custom_path) != 0:
        utils.create_lct_directory(os.getcwd().join(custom_path), output_path)
    else:
        utils.create_lct_directory(os.getcwd(), output_path)

    #Extract data from TFRecord File
    dataset = tf.data.TFRecordDataset(waymo_path,'')

    #Initialize LiDAR camera dictionarys
    translations = {}
    rotations = {}

    #Extracts RGB data
    print("Converting RGB Images...")
    extract_rgb(output_path, waymo_path)

    #Loop through each frame
    frame_num = 0
    for data in dataset:
        frame = open_dataset.Frame()
        frame.ParseFromString(bytearray(data.numpy()))
        if frame_num == 0:
            setup_lidar(frame, output_path, translations, rotations)
        
        #At this point have one frame imported as 'frame'
        extract_lidar(frame, frame_num, output_path, translations, rotations)
        extract_ego(frame, frame_num, output_path)
        extract_bounding(frame,frame_num,output_path)
        frame_num += 1


    
