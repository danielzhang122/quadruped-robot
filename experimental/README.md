# Experimental

Earlier attempts, kept for reference. **None of this is needed to run the robot, and none of it is known to work.**

| Folder | What | State |
|---|---|---|
| `rl/` | Reinforcement learning: `train.py` trains a PPO walking policy (stable-baselines3) in MuJoCo; `watch.py` plays back `quadruped_policy.zip` | Didn't learn to walk. The saved policy was trained on an older `robot.xml`, so it may not match the current model |
| `pose-tools/` | `find_pose.py` (pose the robot in the viewer and print joint angles) and `pose_tuner.py` (try a standing pose) | Untested since the move; they load `../../mujoco/robot.xml` |
| `urdf-conversion/` | One-off scripts used to turn the URDF into `robot.xml` and add actuators, plus intermediate URDFs | Historical only. The scripts still contain the old paths and part names, and would **overwrite** a `robot.xml` with an outdated model. Don't run them |
| `isaac-sim/` | NVIDIA Isaac Sim USD export of the robot | Untested. The files keep their original `forurdf2` names because they reference each other by filename |

The RL scripts need extra packages: `pip install gymnasium stable-baselines3 torch`.
