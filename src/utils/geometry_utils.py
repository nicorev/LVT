"""
geometry_utils.py

General use geometry utils
"""

import numpy as np
from scipy.spatial.transform import Rotation as R
import math

ORIGIN = 0
SIZE = 1
ROTATION = 2
ANNOTATION = 3
CONFIDENCE = 4
COLOR = 5

def translation_and_rotation(transform_matrix):
    """Converts tranformation matrix to a translation and rotation our conversion scripts can use
    Args:
        transform_matrix: 4x4 transform matrix as a numpy array
    
    Returns:
        translation: 1x3 translation vector
        rotation: 1x4 rotation quaternion
    """

    # Extract the first 3 entries in the last column as the translation
    translation = tuple(transform_matrix[:3, -1])

    # Extract the 3x3 rotation matrix from the upper left
    rotation_matrix = transform_matrix[:3, :3]

    # Convert rotation matrix to a quaternion
    quat = R.from_matrix(rotation_matrix)
    
    #Change quaternion from (x,y,z,w) to (w,x,y,z) which is what LVT wants
    rotation = (quat.as_quat()[3], quat.as_quat()[0], quat.as_quat()[1], quat.as_quat()[2])
    
    return translation, rotation

#Returns true if two axis-aligned 3D bounding boxes are overlapping
def is_overlapping(box1, box2):
    #Algorithm taken from https://developer.mozilla.org/en-US/docs/Games/Techniques/3D_collision_detection
    o1 = box1['origin']
    s1 = box1['size']
    o2 = box2['origin']
    s2 = box2['size']
    #loop through x, y, z axes
    for i in range(3):
        a_max = o1[i] + (s1[i]/2)
        a_min = o1[i] - (s1[i]/2)
        b_max = o2[i] + (s2[i]/2)
        b_min = o2[i] - (s2[i]/2)
        if not (a_min <= b_max and a_max >= b_min):
            return False
    return True

def box_dist(box1, box2):
    d_x = (box1['origin'][0] - box2['origin'][0]) ** 2
    d_y = (box1['origin'][1] - box2['origin'][1]) ** 2
    d_z = (box1['origin'][2] - box2['origin'][2]) ** 2
    return math.sqrt(d_x + d_y + d_z)