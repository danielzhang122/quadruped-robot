xml_path = r"C:\Users\zhang\Downloads\urdfwithlimitsrevidek\forurdf2_description\mujoco\meshes\robot.xml"

with open(xml_path, "r") as f:
    content = f.read()

import re

# Replace any existing actuator block with high-kp position actuators
new_actuators = """  <actuator>
    <position name="frontRightHip" joint="frontRightHip" kp="100" ctrlrange="-2.356 0.785"/>
    <position name="frontRightMid" joint="frontRightMid" kp="100" ctrlrange="-1.571 1.571"/>
    <position name="frontRightEnd" joint="frontRightEnd" kp="100" ctrlrange="-3.142 0.0"/>
    <position name="backRightHip"  joint="backRightHip"  kp="100" ctrlrange="-0.785 2.356"/>
    <position name="backRightMid"  joint="backRightMid"  kp="100" ctrlrange="-1.571 1.571"/>
    <position name="backRightEnd"  joint="backRightEnd"  kp="100" ctrlrange="0.0 3.142"/>
    <position name="frontLeftHip"  joint="frontLeftHip"  kp="100" ctrlrange="-0.785 2.356"/>
    <position name="frontLeftMid"  joint="frontLeftMid"  kp="100" ctrlrange="-1.571 1.571"/>
    <position name="frontLeftEnd"  joint="frontLeftEnd"  kp="100" ctrlrange="0.0 3.142"/>
    <position name="backLeftHip"   joint="backLeftHip"   kp="100" ctrlrange="-2.356 0.785"/>
    <position name="backLeftMid"   joint="backLeftMid"   kp="100" ctrlrange="-1.571 1.571"/>
    <position name="backLeftEnd"   joint="backLeftEnd"   kp="100" ctrlrange="-3.142 0.0"/>
  </actuator>"""

content = re.sub(r'<actuator>.*?</actuator>', new_actuators, content, flags=re.DOTALL)

with open(xml_path, "w") as f:
    f.write(content)
print("Done! kp set to 100.")