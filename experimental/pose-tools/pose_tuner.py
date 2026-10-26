"""
Live pose tuner - change values and restart to see changes.
Run: python pose_tuner.py
"""
import mujoco
import mujoco.viewer
import time
from pathlib import Path

XML = str(Path(__file__).resolve().parents[2] / "mujoco" / "robot.xml")
model = mujoco.MjModel.from_xml_path(XML)
data  = mujoco.MjData(model)

# -----------------------------------------------------------------------
# TUNE THESE — restart script to see changes
# hip = fore/aft swing, mid = upper leg, end = lower leg
# -----------------------------------------------------------------------
POSE = {
    'FR': [ 0.0,   0.4,  -0.8],
    'BR': [ 0.0,  -0.4,   0.8],
    'FL': [ 0.0,  -0.4,   0.8],
    'BL': [ 0.0,   0.4,  -0.8],
}
# -----------------------------------------------------------------------

joint_map = {
    'FR': ['frontRightHip', 'frontRightMid', 'frontRightEnd'],
    'BR': ['backRightHip',  'backRightMid',  'backRightEnd'],
    'FL': ['frontLeftHip',  'frontLeftMid',  'frontLeftEnd'],
    'BL': ['backLeftHip',   'backLeftMid',   'backLeftEnd'],
}

print("Current pose:")
for leg, a in POSE.items():
    print(f"  {leg}: hip={a[0]}  mid={a[1]}  end={a[2]}")
print()
print("Edit POSE values in pose_tuner.py and restart to see changes.")
print("Close viewer when done and copy the angles into ik_controller.py")

viewer = mujoco.viewer.launch_passive(model, data)

for leg, angles in POSE.items():
    for jname, angle in zip(joint_map[leg], angles):
        aid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, jname)
        if aid >= 0:
            data.ctrl[aid] = angle

# Hold pose without physics so it doesn't fall
while viewer.is_running():
    mujoco.mj_forward(model, data)  # kinematics only, no physics
    viewer.sync()
    time.sleep(0.02)