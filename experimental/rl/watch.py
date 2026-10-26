import numpy as np
import mujoco
import mujoco.viewer
import time
from pathlib import Path
from stable_baselines3 import PPO
from train import QuadrupedEnv

XML_PATH   = str(Path(__file__).resolve().parents[2] / "mujoco" / "robot.xml")
POLICY_PATH = str(Path(__file__).resolve().parent / "quadruped_policy")

print("Loading policy...")
model = PPO.load(POLICY_PATH)

print("Loading environment...")
env    = QuadrupedEnv(randomize=False, fixed_cmd=[0.3, 0.0, 0.0])  # walk forward
viewer = mujoco.viewer.launch_passive(env.model, env.data)

print("Watching! Close the viewer window to quit.")
print("Commands: forward [0.3, 0, 0] — change fixed_cmd in script for other directions")

while viewer.is_running():
    obs, _ = env.reset()
    while viewer.is_running():
        action, _ = model.predict(obs, deterministic=True)
        obs, _, terminated, truncated, _ = env.step(action)
        viewer.sync()
        time.sleep(env.model.opt.timestep)  # real-time playback
        if terminated or truncated:
            break

print("Done!")
