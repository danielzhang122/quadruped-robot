import xml.etree.ElementTree as ET

xml_path = r"C:\Users\zhang\Downloads\urdfwithlimitsrevidek\forurdf2_description\mujoco\meshes\robot.xml"

tree = ET.parse(xml_path)
root = tree.getroot()

# Find ALL joints anywhere in the tree
print("All joints found in XML:")
joints = []
for joint in root.iter("joint"):
    name = joint.get("name", "")
    jtype = joint.get("type", "hinge")  # MuJoCo defaults to hinge
    print(f"  name='{name}' type='{jtype}'")
    if name and jtype not in ("free", "fixed"):
        joints.append(name)

print(f"\nControllable joints: {joints}")

# Remove existing actuator block if any
for act in root.findall("actuator"):
    root.remove(act)

if joints:
    actuator_el = ET.SubElement(root, "actuator")
    for name in joints:
        ET.SubElement(actuator_el, "motor", name=name, joint=name, gear="1", ctrllimited="true", ctrlrange="-1 1")
    tree.write(xml_path)
    print(f"\nDone! Added {len(joints)} actuators to robot.xml")
else:
    print("\nNo joints found - printing full XML structure for debugging:")
    ET.dump(root)
