import numpy as np
import mujoco
import mujoco.viewer
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv
import torch
from collections import defaultdict
from pathlib import Path

XML_PATH = str(Path(__file__).resolve().parents[2] / "mujoco" / "robot.xml")

TARGET_HEIGHT   = 0.10
HEIGHT_SIGMA    = 0.03
MAX_SERVO_DELTA = np.deg2rad(60) * 0.002
GAIT_FREQ       = 2.0
SIM_TIMESTEP    = 0.002

# Symmetry pairs: FR(0-2)↔FL(6-8), BR(3-5)↔BL(9-11)
SYM_PAIR_A = (slice(0, 3), slice(6, 9))
SYM_PAIR_B = (slice(3, 6), slice(9, 12))

# Trot diagonal pairs
GAIT_PAIR_0 = [0, 3]   # FR + BL (phase 0)
GAIT_PAIR_1 = [2, 1]   # FL + BR (phase π)


class QuadrupedEnv(gym.Env):
    def __init__(self, randomize=True, fixed_cmd=None, curriculum_level=0.0):
        super().__init__()
        self.randomize        = randomize
        self.fixed_cmd        = fixed_cmd
        self.curriculum_level = curriculum_level
        self.model = mujoco.MjModel.from_xml_path(XML_PATH)
        self.data  = mujoco.MjData(self.model)
        self.step_count   = 0
        self.prev_action  = np.zeros(self.model.nu)
        self.prev_vel     = np.zeros(self.model.nu)
        self.cmd          = np.zeros(3)
        self.push_timer   = 0
        self.max_steps    = 200

        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(self.model.nu,), dtype=np.float32
        )
        obs_size = (self.model.nq - 2) + self.model.nv + 3 + 4
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(obs_size,), dtype=np.float32
        )

        self.default_mass     = self.model.body_mass.copy()
        self.default_damping  = self.model.dof_damping.copy()
        self.default_friction = self.model.geom_friction.copy()
        self.default_gear     = self.model.actuator_gear.copy()
        self.foot_geom_ids    = self._find_foot_geoms()

    def _find_foot_geoms(self):
        ids = []
        foot_names = ["fr_end", "br_end", "fl_end", "bl_end"]
        for name in foot_names:
            for i in range(self.model.ngeom):
                gname = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_GEOM, i)
                if gname and name.lower() in gname.lower():
                    ids.append(i)
                    break
            else:
                ids.append(-1)
        return ids

    def _get_foot_contacts(self):
        contacts = np.zeros(4)
        for c in range(self.data.ncon):
            con = self.data.contact[c]
            for i, gid in enumerate(self.foot_geom_ids):
                if gid != -1 and (con.geom1 == gid or con.geom2 == gid):
                    contacts[i] = 1.0
        return contacts

    def _randomize_domain(self):
        lvl = self.curriculum_level
        mass_var     = 0.05 + 0.15 * lvl
        damping_var  = 0.05 + 0.25 * lvl
        friction_var = 0.1  + 0.7  * lvl
        gear_var     = 0.05 + 0.15 * lvl
        self.model.body_mass[:]     = self.default_mass     * np.random.uniform(1-mass_var,     1+mass_var,     self.default_mass.shape)
        self.model.dof_damping[:]   = self.default_damping  * np.random.uniform(1-damping_var,  1+damping_var,  self.default_damping.shape)
        self.model.geom_friction[:] = self.default_friction * np.random.uniform(1-friction_var, 1+friction_var, self.default_friction.shape)
        self.model.actuator_gear[:] = self.default_gear     * np.random.uniform(1-gear_var,     1+gear_var,     self.default_gear.shape)

    def _sample_cmd(self):
        if self.fixed_cmd is not None:
            return np.array(self.fixed_cmd, dtype=np.float32)
        lvl    = self.curriculum_level
        vx_max  = 0.1 + 0.4 * lvl
        vy_max  = 0.0 + 0.3 * lvl
        yaw_max = 0.0 + 1.0 * lvl
        return np.array([
            np.random.uniform(-vx_max,  vx_max),
            np.random.uniform(-vy_max,  vy_max),
            np.random.uniform(-yaw_max, yaw_max),
        ], dtype=np.float32)

    def _random_initial_pose(self):
        lvl = self.curriculum_level
        self.data.qpos[7:] += np.random.uniform(-0.3*lvl, 0.3*lvl, self.model.nq - 7)
        yaw = np.random.uniform(-np.pi * lvl, np.pi * lvl)
        self.data.qpos[3] = np.cos(yaw / 2)
        self.data.qpos[6] = np.sin(yaw / 2)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        if self.randomize:
            self._randomize_domain()
        self._random_initial_pose()
        self.max_steps   = int(200 + 800 * self.curriculum_level)
        mujoco.mj_forward(self.model, self.data)
        self.step_count  = 0
        self.prev_action = np.zeros(self.model.nu)
        self.prev_vel    = np.zeros(self.model.nu)
        self.cmd         = self._sample_cmd()
        self.push_timer  = np.random.randint(50, 200)
        return self._get_obs(), {}

    def _get_obs(self):
        pos_obs       = self.data.qpos[2:]
        vel_obs       = self.data.qvel
        foot_contacts = self._get_foot_contacts()
        noise         = np.random.normal(0, 0.01, len(pos_obs) + len(vel_obs))
        obs_clean     = np.concatenate([pos_obs, vel_obs])
        return np.concatenate([obs_clean + noise, self.cmd, foot_contacts]).astype(np.float32)

    def _get_upright_reward(self):
        base_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "base_link")
        if base_id < 0:
            base_id = 1
        xmat      = self.data.xmat[base_id]
        body_up_z = xmat[8]   # z-col of rotation matrix = dot with world up [0,0,1]
        return float(np.clip(body_up_z, 0.0, 1.0))

    def _get_phase_gait_reward(self, foot_contacts):
        t     = self.step_count * SIM_TIMESTEP
        phase = 2.0 * np.pi * GAIT_FREQ * t
        pair0_expected = 1.0 if np.sin(phase)        >= 0 else 0.0
        pair1_expected = 1.0 if np.sin(phase + np.pi) >= 0 else 0.0
        reward = 0.0
        for fi in GAIT_PAIR_0:
            reward += 0.15 * (1.0 - abs(foot_contacts[fi] - pair0_expected))
        for fi in GAIT_PAIR_1:
            reward += 0.15 * (1.0 - abs(foot_contacts[fi] - pair1_expected))
        return reward

    def _get_joint_limit_penalty(self, action):
        overshoot = np.maximum(np.abs(action) - 0.9, 0.0)
        return float(0.5 * np.sum(np.square(overshoot)))

    def _resample_cmd_maybe(self):
        if self.step_count % 100 == 0 and np.random.rand() < 0.2:
            self.cmd = self._sample_cmd()

    def _apply_push_maybe(self):
        if self.step_count == self.push_timer and self.curriculum_level > 0.3:
            force_scale = 2.0 * self.curriculum_level
            self.data.qvel[0:3] += np.random.uniform(-force_scale, force_scale, 3)

    def step(self, action):
        delta             = np.clip(action - self.prev_action, -MAX_SERVO_DELTA, MAX_SERVO_DELTA)
        clipped_action    = self.prev_action + delta
        smoothed_action   = 0.8 * self.prev_action + 0.2 * clipped_action
        self.data.ctrl[:] = smoothed_action

        self._apply_push_maybe()
        mujoco.mj_step(self.model, self.data)
        self._resample_cmd_maybe()
        self.step_count += 1

        obs           = self._get_obs()
        z_pos         = self.data.qpos[2]
        linvel        = self.data.qvel[0:3]
        angvel        = self.data.qvel[3:6]
        joint_vel     = self.data.qvel[6:]
        foot_contacts = self._get_foot_contacts()

        vx_err  = (linvel[0] - self.cmd[0]) ** 2
        vy_err  = (linvel[1] - self.cmd[1]) ** 2
        yaw_err = (angvel[2] - self.cmd[2]) ** 2
        r_tracking = (
            4.0 * np.exp(-vx_err  / 0.25) +
            2.0 * np.exp(-vy_err  / 0.25) +
            1.0 * np.exp(-yaw_err / 0.25)
        )
        r_orientation = self._get_upright_reward()
        # Height reward only counts when upright — prevents lying-still hacking
        r_height      = float(np.exp(-0.5 * ((z_pos - TARGET_HEIGHT) / HEIGHT_SIGMA) ** 2)) * r_orientation
        r_gait        = self._get_phase_gait_reward(foot_contacts)
        r_survival    = 0.0   # removed: was causing lying-still reward hacking
        p_symmetry    = 0.05 * (
            float(np.sum(np.square(smoothed_action[SYM_PAIR_A[0]] - smoothed_action[SYM_PAIR_A[1]]))) +
            float(np.sum(np.square(smoothed_action[SYM_PAIR_B[0]] - smoothed_action[SYM_PAIR_B[1]])))
        )
        p_stability   = 0.1  * float(angvel[0]**2 + angvel[1]**2)
        p_energy      = 0.05 * float(np.sum(np.square(smoothed_action)))
        p_jitter      = 0.10 * float(np.sum(np.square(smoothed_action - self.prev_action)))
        p_accel       = 0.01 * float(np.sum(np.square(joint_vel - self.prev_vel)))
        p_limits      = self._get_joint_limit_penalty(smoothed_action)

        reward = (r_tracking + r_height + r_orientation + r_gait + r_survival
                  - p_symmetry - p_stability - p_energy - p_jitter - p_accel - p_limits)

        self.prev_action = smoothed_action.copy()
        self.prev_vel    = joint_vel.copy()

        min_height = 0.09 - 0.02 * (1.0 - self.curriculum_level)  # tighter floor
        terminated = bool(z_pos < min_height)
        truncated  = self.step_count >= self.max_steps

        info = {
            "reward/tracking":    r_tracking,
            "reward/height":      r_height,
            "reward/orientation": r_orientation,
            "reward/gait":        r_gait,
            "reward/survival":    r_survival,
            "penalty/symmetry":   p_symmetry,
            "penalty/stability":  p_stability,
            "penalty/energy":     p_energy,
            "penalty/jitter":     p_jitter,
            "penalty/accel":      p_accel,
            "penalty/limits":     p_limits,
            "curriculum_level":   self.curriculum_level,
        }
        return obs, reward, terminated, truncated, info


# ----------------------------------------------------------------------
class CurriculumCallbackWithViewer(BaseCallback):
    """
    - Updates curriculum_level across all SubprocVecEnv workers
    - Logs per-component rewards to TensorBoard every log_interval steps
    - Renders current policy in a live MuJoCo viewer every render_interval steps
    """
    def __init__(self, total_timesteps, log_interval=2048, render_interval=8192):
        super().__init__()
        self.total_timesteps = total_timesteps
        self.log_interval    = log_interval
        self.render_interval = render_interval
        self._component_buf  = defaultdict(list)

        # Separate render env in main process
        self.render_env = QuadrupedEnv(randomize=False)
        self.viewer     = mujoco.viewer.launch_passive(
                              self.render_env.model,
                              self.render_env.data)

    def _on_step(self):
        if not self.viewer.is_running():
            return False   # stop training if viewer closed

        # Update curriculum on all workers
        level = self.num_timesteps / self.total_timesteps
        self.training_env.env_method("__setattr__", "curriculum_level", level)

        # Buffer reward components
        for info in self.locals.get("infos", []):
            for key, val in info.items():
                if key.startswith("reward/") or key.startswith("penalty/") or key == "curriculum_level":
                    self._component_buf[key].append(val)

        # Log to TensorBoard
        if self.num_timesteps % self.log_interval == 0 and self._component_buf:
            for key, vals in self._component_buf.items():
                self.logger.record(f"custom/{key}", float(np.mean(vals)))
            self._component_buf.clear()

        # Render current policy
        if self.num_timesteps % self.render_interval == 0:
            obs, _ = self.render_env.reset()
            for _ in range(500):
                action, _ = self.model.predict(obs, deterministic=True)
                obs, _, terminated, truncated, _ = self.render_env.step(action)
                self.viewer.sync()
                if terminated or truncated:
                    break

        return True

    def _on_training_end(self):
        self.viewer.close()


# ----------------------------------------------------------------------
def make_env(rank, randomize=True):
    def _init():
        env = QuadrupedEnv(randomize=randomize)
        env.reset(seed=rank)
        return env
    return _init


# ----------------------------------------------------------------------
if __name__ == "__main__":
    TOTAL_STEPS = 10_000_000
    N_ENVS      = 8

    print(f"Launching {N_ENVS} parallel environments...")
    vec_env = SubprocVecEnv([make_env(i) for i in range(N_ENVS)])

    print(f"Action space:      {vec_env.action_space.shape}")
    print(f"Observation space: {vec_env.observation_space.shape}")
    print(f"Using CPU (faster for MLP policies)")

    model = PPO(
        "MlpPolicy",
        vec_env,
        verbose=1,
        device="cpu",   # MLP policies run faster on CPU than GPU
        tensorboard_log="./logs/",
        n_steps=512,
        batch_size=256,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        # progress_remaining goes 1.0→0.0, so LR decays 3e-4→0
        # standard PPO schedule: large updates early, fine-tuning late
        learning_rate=lambda progress_remaining: 3e-4 * progress_remaining,
        policy_kwargs=dict(
            net_arch=[512, 512, 256],
            activation_fn=torch.nn.ELU,
            ortho_init=True,
        )
    )

    print("Starting training! Viewer window will open.")
    print("Tip: run 'tensorboard --logdir=./logs' to monitor reward components")
    callback = CurriculumCallbackWithViewer(TOTAL_STEPS)
    model.learn(total_timesteps=TOTAL_STEPS, callback=callback)
    model.save(str(Path(__file__).resolve().parent / "quadruped_policy"))
    print("Done! Policy saved as quadruped_policy.zip")