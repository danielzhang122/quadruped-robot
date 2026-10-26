"""
Run this first to find the default joint positions from MuJoCo.
It opens the viewer — use the MuJoCo UI to pose the robot how you want it to stand,
then press ENTER in this terminal to print the joint angles.
"""
import mujoco
import mujoco.viewer
import time
from pathlib import Path

XML = str(Path(__file__).resolve().parents[2] / "mujoco" / "robot.xml")
model = mujoco.MjModel.from_xml_path(XML)
data  = mujoco.MjData(model)

joint_names = [
    ('FR', ['frontRightHip', 'frontRightMid', 'frontRightEnd']),
    ('BR', ['backRightHip',  'backRightMid',  'backRightEnd']),
    ('FL', ['frontLeftHip',  'frontLeftMid',  'frontLeftEnd']),
    ('BL', ['backLeftHip',   'backLeftMid',   'backLeftEnd']),
]

# Just set all joints to 0 and print what that looks like
print("Opening viewer with all joints at 0...")
print("Press ENTER here to print current joint angles")

viewer = mujoco.viewer.launch_passive(model, data)

# Run sim for a bit to settle
for _ in range(200):
    mujoco.mj_step(model, data)
    viewer.sync()

input("Press ENTER to print joint angles...")

print("\nCurrent joint angles:")
print("REST_POSE = {")
for leg, names in joint_names:
    angles = []
    for n in names:
        jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)
        if jid >= 0:
            angles.append(round(data.qpos[model.jnt_qposadr[jid]], 4))
        else:
            angles.append(0.0)
    print(f"    '{leg}': {angles},")
print("}")

viewer.close()
