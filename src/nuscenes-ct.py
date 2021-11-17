"""
nuscenes-ct.py

Conversion tool to bring nuscenes dataset into LVT. 
"""

import getopt
import sys
import os
import utils

from nuscenes.nuscenes import NuScenes

from nuscenes.utils.data_classes import LidarPointCloud
from nuscenes.utils.data_classes import Quaternion
from nuscenes.utils.data_classes import Box

import numpy as np

# Parse CLI args and validate input
def parse_options():

    input_path = ""
    output_path = ""
    scene_name = ""
    parse_options = ""
    
    # Read in flags passed in with command line argument
    # Make sure that options which need an argument (namely -f for input file path and -o for output file path) have them
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hf:o:s:", "help")
    except getopt.GetoptError as err:
        print(err)
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print("use -f to specify directory of nuScenes dataset")
            print("use -o to specify the path where the LVT dataset will go")
            print("use -s to specify the name of the scene")
            sys.exit(2)
        elif opt == "-f": #and len(opts) == 2:
            input_path = arg
        elif opt == "-o": #and len(opts) == 2:
            output_path = arg
        elif opt == "-s":
            scene_name = arg
        else:
            # Only reach here if you were passed in a single option; consider this invalid input since we need both file paths
            print("Invalid set of arguments entered. Please refer to -h flag for more information.")
            sys.exit(2)

    return (input_path, output_path, scene_name)

# Used to check if file is valid nuScenes file
def validate_io_paths(input_path, output_path):

    # First check that the input path (1) exists, and (2) is a valid nuScenes database
    try:
        nusc = NuScenes(version='v1.0-mini', dataroot=input_path, verbose=True)
    except AssertionError as error:
        print("Invalid argument passed in as nuScenes file.")
        print("DEBUG: stacktrace is as follows.", str(error))

    # Output directory path is validated in utils.create_lct_directory()
    utils.create_lct_directory(os.getcwd(), output_path)

def extract_ego(nusc, sample, frame_num, output_path):
    sensor = nusc.get('sample_data', sample['data']['LIDAR_TOP'])
    poserecord = nusc.get('ego_pose', sensor['ego_pose_token'])

    full_path = os.path.join(os.getcwd(), output_path)
    utils.create_ego_directory(full_path, frame_num, poserecord['translation'], poserecord['rotation'])

def extract_bounding(nusc, sample, frame_num, target_path):
    origins = []
    sizes = []
    rotations = []
    annotation_names = []
    confidences = []
    
    for i in range(0, len(sample['anns']) - 1):
        token = sample['anns'][i]
        annotation_metadata = nusc.get('sample_annotation', token)
        #Create nuscenes box object so we can easily transform this box to the vehicle frame that our dataset requires
        box = Box(annotation_metadata['translation'], annotation_metadata['size'], Quaternion(annotation_metadata['rotation']))
        sensor = nusc.get('sample_data', sample['data']['LIDAR_TOP'])
        poserecord = nusc.get('ego_pose', sensor['ego_pose_token'])
        
        box.translate(-np.array(poserecord['translation']))
        box.rotate(Quaternion(poserecord['rotation']).inverse)


        origins.append(box.center.tolist())
        sizes.append(annotation_metadata['size'])
        rotations.append(box.orientation.q.tolist())
        annotation_names.append(annotation_metadata['category_name'])
        confidences.append(100)
        
    utils.create_frame_bounding_directory(target_path, frame_num, origins, sizes, rotations, annotation_names, confidences)

def extract_pred_bounding(sample, frame_num, target_path):
    origins = []
    sizes = []
    rotations = []
    annotation_names = []
    confidences = []
    
    for i in range(0, len(sample['anns']) - 1):
        token = sample['anns'][i]
        annotation_metadata = nusc.get('sample_annotation', token)
        origins.append(annotation_metadata['translation'])
        sizes.append(annotation_metadata['size'])
        rotations.append(annotation_metadata['rotation'])
        annotation_names.append(annotation_metadata['category_name'])
        confidences.append(100)
        
    utils.create_frame_predicted_directory(target_path, frame_num, origins, sizes, rotations, annotation_names, confidences)


def extract_rgb(nusc, sample, frame_num, target_path):
    camera_list = ["CAM_FRONT", "CAM_FRONT_RIGHT", "CAM_BACK_RIGHT", "CAM_BACK", "CAM_BACK_LEFT", "CAM_FRONT_LEFT"]
    #For each camera sensor
    for camera in camera_list:
        (path, boxes, camera_intrinsic) = nusc.get_sample_data(sample['data'][camera])
        utils.add_rgb_frame_from_jpg(target_path, camera, frame_num, path)

def extract_lidar(nusc, sample, frame_num, target_path):
    """Used to extract the LIDAR pointcloud information from the nuScenes dataset
    Args:
        nusc: NuScenes api object for getting info related to LiDAR data
        sample: All the sensor information
        frame_num: Frame number
        target_path: Output directory path where data will be written to
    """
    
    # We'll need to get all the information we need to pass to utils.add_lidar_frame()
    # Get the points, translation, and rotation info using our nusc input
    sensor = nusc.get('sample_data', sample['data']["LIDAR_TOP"])
    cs_record = nusc.get('calibrated_sensor', sensor['calibrated_sensor_token'])
    (path, boxes, camera_intrinsic) = nusc.get_sample_data(sample['data']["LIDAR_TOP"])
    points = LidarPointCloud.from_file(path)
    translation = cs_record['translation']
    rotation = cs_record['rotation']

    #Transform points to Vehicle Frame
    points.rotate(Quaternion(rotation).rotation_matrix)
    points.translate(translation)
    # Reshape points
    points = np.transpose(points.points[:3, :])

    utils.add_lidar_frame(target_path, "LIDAR_TOP", frame_num, points, translation, rotation)

        
    
# Driver for nuscenes conversion tool
if __name__ == "__main__":

    # Read in input database and output directory paths
    (input_path, output_path, scene_name) = parse_options()
    
    # Debug print statement to check that they were read in correctly
    # print(input_path, output_path)

    # Validate whether the database path passed in is valid and if the output directory path is valid
    # If the output directory exists, then use that directory. Otherwise, create a new directory at the
    # specified path. 
    

    validate_io_paths(input_path, output_path)
    nusc = NuScenes('v1.0-mini', input_path, True)
    nusc.list_scenes()
    scene_token = nusc.field2token('scene', 'name', scene_name)[0]
    scene = nusc.get('scene', scene_token)
    sample = nusc.get('sample', scene['first_sample_token'])
    frame_num = 0

    #Set up Camera Directories
    camera_list = ["CAM_FRONT", "CAM_FRONT_RIGHT", "CAM_BACK_RIGHT", "CAM_BACK", "CAM_BACK_LEFT", "CAM_FRONT_LEFT"]
    for camera in camera_list:
        sensor = nusc.get('sample_data', sample['data'][camera])
        cs_record = nusc.get('calibrated_sensor', sensor['calibrated_sensor_token'])
        utils.create_rgb_sensor_directory(output_path, camera, cs_record['translation'], cs_record['rotation'], cs_record['camera_intrinsic'])

    #Set up LiDAR Directory
    utils.create_lidar_sensor_directory(output_path, "LIDAR_TOP")

    while sample['next'] != '':
        #CALL FUNCTIONS HERE. the variable 'sample' is the frame
        extract_ego(nusc, sample, frame_num, output_path)
        extract_bounding(nusc, sample, frame_num, output_path)
        extract_pred_bounding(nusc, sample, frame_num, output_path)
        extract_rgb(nusc, sample, frame_num, output_path)
        extract_lidar(nusc, sample, frame_num, output_path)
        frame_num += 1
        sample = nusc.get('sample', sample['next'])

    
