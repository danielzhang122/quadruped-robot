xml_path = r"C:\Users\zhang\Downloads\urdfwithlimitsrevidek\forurdf2_description\mujoco\meshes\robot.xml"

xml_content = '''<mujoco model="forurdf2">
  <compiler angle="radian"/>

  <option gravity="0 0 -9.81" timestep="0.002"/>

  <asset>
    <mesh name="base_link" content_type="model/stl" file="base_link.stl" scale="0.001 0.001 0.001"/>
    <mesh name="FRhip_1" content_type="model/stl" file="FRhip_1.stl" scale="0.001 0.001 0.001"/>
    <mesh name="FRmid_1" content_type="model/stl" file="FRmid_1.stl" scale="0.001 0.001 0.001"/>
    <mesh name="FRend_1" content_type="model/stl" file="FRend_1.stl" scale="0.001 0.001 0.001"/>
    <mesh name="backrighthip_1" content_type="model/stl" file="backrighthip_1.stl" scale="0.001 0.001 0.001"/>
    <mesh name="brmid_1" content_type="model/stl" file="brmid_1.stl" scale="0.001 0.001 0.001"/>
    <mesh name="brend_1" content_type="model/stl" file="brend_1.stl" scale="0.001 0.001 0.001"/>
    <mesh name="flhip_1" content_type="model/stl" file="flhip_1.stl" scale="0.001 0.001 0.001"/>
    <mesh name="flmid_1" content_type="model/stl" file="flmid_1.stl" scale="0.001 0.001 0.001"/>
    <mesh name="flend_1" content_type="model/stl" file="flend_1.stl" scale="0.001 0.001 0.001"/>
    <mesh name="blhip_1" content_type="model/stl" file="blhip_1.stl" scale="0.001 0.001 0.001"/>
    <mesh name="blmid_1" content_type="model/stl" file="blmid_1.stl" scale="0.001 0.001 0.001"/>
    <mesh name="blend_1" content_type="model/stl" file="blend_1.stl" scale="0.001 0.001 0.001"/>
    <mesh name="baseUpper_1" content_type="model/stl" file="baseUpper_1.stl" scale="0.001 0.001 0.001"/>
  </asset>

  <worldbody>
    <light diffuse=".5 .5 .5" pos="0 0 3" dir="0 0 -1"/>
    <geom name="ground" type="plane" size="10 10 0.1" rgba="0.8 0.8 0.8 1"/>

    <body name="base_link" pos="0 0 0.15">
      <freejoint name="root"/>
      <geom type="mesh" mesh="base_link"/>
      <geom type="mesh" mesh="baseUpper_1"/>

      <body name="FRhip_1" pos="0.065762 -0.05514 -0.038083">
        <inertial pos="-0.00668492 -0.0276808 0.0119461" quat="0.965743 0.207359 -0.0300658 -0.153095" mass="0.0441843" diaginertia="2.99304e-05 1.92258e-05 1.66333e-05"/>
        <joint name="frontRightHip" pos="0 0 0" axis="0 0 -1" range="-2.35619 0.785398" actuatorfrcrange="-100 100"/>
        <geom pos="-0.065762 0.05514 0.038083" type="mesh" mesh="FRhip_1"/>
        <body name="FRmid_1" pos="-0.03 -0.041341 0.00755">
          <inertial pos="0.0243043 -0.0370653 -3.7597e-07" quat="0.5 0.5 -0.5 0.5" mass="0.0356783" diaginertia="4.69872e-05 2.72823e-05 2.18994e-05"/>
          <joint name="frontRightMid" pos="0 0 0" axis="-1 0 0" range="-1.5708 1.5708" actuatorfrcrange="-100 100"/>
          <geom pos="-0.035762 0.096481 0.030533" type="mesh" mesh="FRmid_1"/>
          <body name="FRend_1" pos="-0.002 -0.074131 0">
            <inertial pos="0.0248621 0.00119021 -0.0180069" quat="0.994646 -0.0397935 -0.0924563 0.0233996" mass="0.0299344" diaginertia="2.27975e-05 2.27196e-05 3.89009e-06"/>
            <joint name="frontRightEnd" pos="0 0 0" axis="1 0 0" range="-3.14159 0" actuatorfrcrange="-100 100"/>
            <geom pos="-0.033762 0.170612 0.030533" type="mesh" mesh="FRend_1"/>
          </body>
        </body>
      </body>

      <body name="backrighthip_1" pos="-0.062496 -0.05514 -0.038083">
        <inertial pos="0.00668428 -0.0276808 0.0119461" quat="0.965744 0.207356 0.0300641 0.153096" mass="0.0441844" diaginertia="2.99305e-05 1.92258e-05 1.66333e-05"/>
        <joint name="backRightHip" pos="0 0 0" axis="0 0 -1" range="-0.785398 2.35619" actuatorfrcrange="-100 100"/>
        <geom pos="0.062496 0.05514 0.038083" type="mesh" mesh="backrighthip_1"/>
        <body name="brmid_1" pos="0.03 -0.041341 0.00755">
          <inertial pos="-0.024305 -0.0370653 -3.75428e-07" quat="0.5 0.5 -0.5 0.5" mass="0.0356783" diaginertia="4.69872e-05 2.72823e-05 2.18995e-05"/>
          <joint name="backRightMid" pos="0 0 0" axis="1 0 0" range="-1.5708 1.5708" actuatorfrcrange="-100 100"/>
          <geom pos="0.032496 0.096481 0.030533" type="mesh" mesh="brmid_1"/>
          <body name="brend_1" pos="0.002 -0.074131 0">
            <inertial pos="-0.0248627 0.00119021 -0.0180069" quat="0.994646 -0.0397935 0.0924563 -0.0233996" mass="0.0299344" diaginertia="2.27975e-05 2.27196e-05 3.89009e-06"/>
            <joint name="backRightEnd" pos="0 0 0" axis="-1 0 0" range="0 3.14159" actuatorfrcrange="-100 100"/>
            <geom pos="0.030496 0.170612 0.030533" type="mesh" mesh="brend_1"/>
          </body>
        </body>
      </body>

      <body name="flhip_1" pos="0.065762 0.051742 -0.038083">
        <inertial pos="-0.0066849 0.02768 0.0119461" quat="0.965744 -0.207356 -0.0300641 0.153096" mass="0.0441844" diaginertia="2.99305e-05 1.92258e-05 1.66333e-05"/>
        <joint name="frontLeftHip" pos="0 0 0" axis="0 0 -1" range="-0.785398 2.35619" actuatorfrcrange="-100 100"/>
        <geom pos="-0.065762 -0.051742 0.038083" type="mesh" mesh="flhip_1"/>
        <body name="flmid_1" pos="-0.03 0.04134 0.00755">
          <inertial pos="0.0243043 0.0370655 -3.75428e-07" quat="0.5 0.5 -0.5 0.5" mass="0.0356783" diaginertia="4.69872e-05 2.72823e-05 2.18995e-05"/>
          <joint name="frontLeftMid" pos="0 0 0" axis="-1 0 0" range="-1.5708 1.5708" actuatorfrcrange="-100 100"/>
          <geom pos="-0.035762 -0.093082 0.030533" type="mesh" mesh="flmid_1"/>
          <body name="flend_1" pos="-0.002 0.074131 0">
            <inertial pos="0.0248621 -0.00118998 -0.0180069" quat="0.994646 0.0397935 -0.0924563 -0.0233996" mass="0.0299344" diaginertia="2.27975e-05 2.27196e-05 3.89009e-06"/>
            <joint name="frontLeftEnd" pos="0 0 0" axis="1 0 0" range="0 3.14159" actuatorfrcrange="-100 100"/>
            <geom pos="-0.033762 -0.167213 0.030533" type="mesh" mesh="flend_1"/>
          </body>
        </body>
      </body>

      <body name="blhip_1" pos="-0.062496 0.051742 -0.038083">
        <inertial pos="0.00668431 0.02768 0.0119461" quat="0.965743 -0.207359 0.0300658 -0.153095" mass="0.0441843" diaginertia="2.99304e-05 1.92258e-05 1.66333e-05"/>
        <joint name="backLeftHip" pos="0 0 0" axis="0 0 -1" range="-2.35619 0.785398" actuatorfrcrange="-100 100"/>
        <geom pos="0.062496 -0.051742 0.038083" type="mesh" mesh="blhip_1"/>
        <body name="blmid_1" pos="0.03 0.04134 0.00755">
          <inertial pos="-0.024305 0.0370655 -3.7597e-07" quat="0.5 0.5 -0.5 0.5" mass="0.0356783" diaginertia="4.69872e-05 2.72823e-05 2.18994e-05"/>
          <joint name="backLeftMid" pos="0 0 0" axis="1 0 0" range="-1.5708 1.5708" actuatorfrcrange="-100 100"/>
          <geom pos="0.032496 -0.093082 0.030533" type="mesh" mesh="blmid_1"/>
          <body name="blend_1" pos="0.002 0.074131 0">
            <inertial pos="-0.0248627 -0.00118998 -0.0180069" quat="0.994646 0.0397935 0.0924563 0.0233996" mass="0.0299344" diaginertia="2.27975e-05 2.27196e-05 3.89009e-06"/>
            <joint name="backLeftEnd" pos="0 0 0" axis="-1 0 0" range="-3.14159 0" actuatorfrcrange="-100 100"/>
            <geom pos="0.030496 -0.167213 0.030533" type="mesh" mesh="blend_1"/>
          </body>
        </body>
      </body>

    </body>
  </worldbody>

  <actuator>
    <motor name="frontRightHip" joint="frontRightHip" gear="1" ctrllimited="true" ctrlrange="-1 1"/>
    <motor name="frontRightMid" joint="frontRightMid" gear="1" ctrllimited="true" ctrlrange="-1 1"/>
    <motor name="frontRightEnd" joint="frontRightEnd" gear="1" ctrllimited="true" ctrlrange="-1 1"/>
    <motor name="backRightHip" joint="backRightHip" gear="1" ctrllimited="true" ctrlrange="-1 1"/>
    <motor name="backRightMid" joint="backRightMid" gear="1" ctrllimited="true" ctrlrange="-1 1"/>
    <motor name="backRightEnd" joint="backRightEnd" gear="1" ctrllimited="true" ctrlrange="-1 1"/>
    <motor name="frontLeftHip" joint="frontLeftHip" gear="1" ctrllimited="true" ctrlrange="-1 1"/>
    <motor name="frontLeftMid" joint="frontLeftMid" gear="1" ctrllimited="true" ctrlrange="-1 1"/>
    <motor name="frontLeftEnd" joint="frontLeftEnd" gear="1" ctrllimited="true" ctrlrange="-1 1"/>
    <motor name="backLeftHip" joint="backLeftHip" gear="1" ctrllimited="true" ctrlrange="-1 1"/>
    <motor name="backLeftMid" joint="backLeftMid" gear="1" ctrllimited="true" ctrlrange="-1 1"/>
    <motor name="backLeftEnd" joint="backLeftEnd" gear="1" ctrllimited="true" ctrlrange="-1 1"/>
  </actuator>

</mujoco>
'''

with open(xml_path, 'w') as f:
    f.write(xml_content)

print("Done! robot.xml rebuilt with ground, gravity, freejoint and actuators.")
