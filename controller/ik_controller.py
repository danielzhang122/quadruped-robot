"""
Quadruped trot gait controller.

Open-loop joint-space trot: each leg follows a sine pattern around a rest pose,
with the diagonal pairs (FR+BL and FL+BR) half a cycle apart. Runs in MuJoCo by
default, or on the real robot (PCA9685 servo board) with --hardware.

All angles are radians in the URDF / MuJoCo joint frame. Joint limits are read
from mujoco/robot.xml, so the sim and the servo mapping always agree.
"""
from __future__ import annotations

import argparse
import math
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_XML = ROOT / "mujoco" / "robot.xml"

# -----------------------------------------------------------------------
# Robot description
# -----------------------------------------------------------------------
LEGS = ('FR', 'BR', 'FL', 'BL')

JOINT_NAMES: dict[str, tuple[str, str, str]] = {
    'FR': ('frontRightHip', 'frontRightMid', 'frontRightEnd'),
    'BR': ('backRightHip',  'backRightMid',  'backRightEnd'),
    'FL': ('frontLeftHip',  'frontLeftMid',  'frontLeftEnd'),
    'BL': ('backLeftHip',   'backLeftMid',   'backLeftEnd'),
}

SERVO_CHANNELS: dict[str, tuple[int, int, int]] = {
    'FR': (0,  1,  2),
    'BR': (3,  4,  5),
    'FL': (6,  7,  8),
    'BL': (9, 10, 11),
}

# Untested on the real robot: flip a joint to True if its servo turns the wrong way.
SERVO_INVERT: dict[str, tuple[bool, bool, bool]] = {leg: (False, False, False) for leg in LEGS}

# Skip a servo write if the angle moved less than this (deg). Hobby servos can't
# resolve finer steps, so this only cuts I2C traffic, not precision.
SERVO_DEADBAND = 0.1

# Standing pose (hip, mid, end). Checked in sim: only the feet touch the
# ground and the base sits about 0.14 m up. The sign of each mid/end value
# also tells the gait which way is "down" / "bend" for that leg.
REST_POSE: dict[str, tuple[float, float, float]] = {
    'FR': (0.0, -0.5, -0.8),
    'BR': (0.0,  0.5,  0.8),
    'FL': (0.0,  0.5,  0.8),
    'BL': (0.0, -0.5, -0.8),
}

# -----------------------------------------------------------------------
# Tunables
# -----------------------------------------------------------------------
DT            = 0.01   # control period (s)
GAIT_FREQ     = 1.5    # steps per second
SWING_HIP     = 0.40   # hip swing amplitude at full stride (rad)
STEP_HEIGHT   = 0.30   # mid-joint lift during swing at full stride (rad)
KNEE_TUCK     = 1.0    # end joint bends this many times the lift during swing
SMOOTHING_TAU = 0.16   # low-pass time constant on joint commands (s)
Z_SPEED       = 0.35   # body height change rate (rad/s on the mid joint)
Z_LIMIT       = 0.4    # max body height offset (rad)
Z_RESET_RATE  = 2.0    # how fast R eases the height back to 0 (1/s)
ACCEL         = 2.0    # command ramp rate (full stride per second)

# Keyboard commands are fractions of a full stride, in [-1, 1].
KEY_VX  = 1.0
KEY_YAW = 1.0


def load_joint_limits(xml_path: Path = MODEL_XML) -> dict[str, tuple[float, float]]:
    """Actuator ctrlrange per joint name, read straight from the MuJoCo model."""
    limits = {}
    for act in ET.parse(xml_path).getroot().iter('position'):
        lo, hi = (float(v) for v in act.get('ctrlrange').split())
        limits[act.get('joint')] = (lo, hi)
    return limits


JOINT_LIMITS = load_joint_limits()


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _sign(x: float) -> float:
    return 1.0 if x >= 0.0 else -1.0


# -----------------------------------------------------------------------
# Gait
# -----------------------------------------------------------------------
@dataclass(frozen=True)
class _LegConsts:
    phase_off: float              # FR+BL at 0, FL+BR at pi
    side: float                   # +1 right legs, -1 left legs (hip axes are mirrored)
    down: float                   # mid-joint direction that pushes the foot down
    bend: float                   # end-joint direction that bends the knee
    rest: tuple[float, float, float]
    lo: tuple[float, float, float]
    hi: tuple[float, float, float]


def _leg_consts(leg: str) -> _LegConsts:
    rest = REST_POSE[leg]
    lims = [JOINT_LIMITS[j] for j in JOINT_NAMES[leg]]
    return _LegConsts(
        phase_off=0.0 if leg in ('FR', 'BL') else math.pi,
        side=1.0 if leg in ('FR', 'BR') else -1.0,
        down=_sign(rest[1]),
        bend=_sign(rest[2]),
        rest=rest,
        lo=tuple(l for l, _ in lims),
        hi=tuple(h for _, h in lims),
    )


_LEG = {leg: _leg_consts(leg) for leg in LEGS}

# Flat per-leg tuples for the gait's hot loop (unpacking beats attribute lookups).
# The pairs are exactly half a cycle apart, so instead of a phase offset each leg
# carries the sign it applies to sin/cos of the shared phase: sin(p + pi) = -sin(p).
_GAIT_LEGS = tuple(
    (leg, 1.0 if k.phase_off == 0.0 else -1.0, k.side, k.down, k.bend, *k.rest, *k.lo, *k.hi)
    for leg, k in _LEG.items()
)
_TWO_PI = 2.0 * math.pi
_OMEGA = _TWO_PI * GAIT_FREQ


class TrotGait:
    def __init__(self) -> None:
        self.phase = 0.0

    def get_joint_angles(
        self, vx: float = 0.0, yaw: float = 0.0, z: float = 0.0, dt: float = DT,
    ) -> dict[str, tuple[float, float, float]]:
        """vx, yaw: fraction of full stride in [-1, 1]. z: body height offset (rad)."""
        vx = _clamp(vx, -1.0, 1.0)
        yaw = _clamp(yaw, -1.0, 1.0)
        stride = min(1.0, math.hypot(vx, yaw))
        if stride > 0.0:
            self.phase = (self.phase + _OMEGA * dt) % _TWO_PI

        # One sin/cos per tick, shared by all four legs.
        sin_p, cos_p = math.sin(self.phase), math.cos(self.phase)
        lift_amp = STEP_HEIGHT * stride

        angles = {}
        for leg, sgn, side, down, bend, r0, r1, r2, lo0, lo1, lo2, hi0, hi1, hi2 in _GAIT_LEGS:
            # Swing on the positive half of the cycle, stance on the negative half.
            s = sgn * sin_p
            lift = s * lift_amp if s > 0.0 else 0.0
            swing = _clamp(vx * side + yaw, -1.0, 1.0)

            hip = r0 + SWING_HIP * sgn * cos_p * swing
            mid = r1 + down * (z - lift)
            end = r2 + bend * (KNEE_TUCK * lift - z)

            angles[leg] = (
                _clamp(hip, lo0, hi0),
                _clamp(mid, lo1, hi1),
                _clamp(end, lo2, hi2),
            )
        return angles


class VelocityRamp:
    """Limits how fast a command can change."""

    def __init__(self, rate: float) -> None:
        self.current = 0.0
        self.rate = rate

    def update(self, target: float, dt: float) -> float:
        step = self.rate * dt
        self.current += _clamp(target - self.current, -step, step)
        return self.current


# -----------------------------------------------------------------------
# Controller (no I/O, so it can be tested without a viewer or keyboard)
# -----------------------------------------------------------------------
@dataclass
class Command:
    vx: float = 0.0
    yaw: float = 0.0
    z_dir: float = 0.0      # -1 lower, +1 raise, 0 hold
    reset_z: bool = False
    estop: bool = False


class Controller:
    def __init__(self, dt: float = DT) -> None:
        self.dt = dt
        self.gait = TrotGait()
        self.vx = VelocityRamp(ACCEL)
        self.yaw = VelocityRamp(ACCEL)
        self.z = 0.0
        self.alpha = dt / (SMOOTHING_TAU + dt)
        self.angles: dict[str, list[float]] = {leg: list(REST_POSE[leg]) for leg in LEGS}

    def step(self, cmd: Command) -> dict[str, list[float]]:
        if cmd.estop:
            # Hold the current pose; the gait phase isn't advanced, so there's no jump on resume.
            self.vx.current = self.yaw.current = 0.0
            return self.angles

        vx = self.vx.update(cmd.vx, self.dt)
        yaw = self.yaw.update(cmd.yaw, self.dt)
        if cmd.reset_z:
            self.z -= self.z * Z_RESET_RATE * self.dt
        else:
            self.z += cmd.z_dir * Z_SPEED * self.dt
        self.z = _clamp(self.z, -Z_LIMIT, Z_LIMIT)

        target = self.gait.get_joint_angles(vx, yaw, self.z, self.dt)
        a = self.alpha
        for leg in LEGS:
            cur, tgt = self.angles[leg], target[leg]
            for i in range(3):
                cur[i] += a * (tgt[i] - cur[i])
        return self.angles

    def ease_to_rest(self, rate: float = 0.05) -> dict[str, list[float]]:
        for leg in LEGS:
            cur, rest = self.angles[leg], REST_POSE[leg]
            for i in range(3):
                cur[i] += (rest[i] - cur[i]) * rate
        return self.angles


# -----------------------------------------------------------------------
# Simulation interface
# -----------------------------------------------------------------------
class SimInterface:
    def __init__(self, xml_path: Path = MODEL_XML, viewer: bool = True) -> None:
        import mujoco
        self.mj = mujoco
        self.model = mujoco.MjModel.from_xml_path(str(xml_path))
        self.data = mujoco.MjData(self.model)
        self.actuator_ids = {
            j: mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, j)
            for names in JOINT_NAMES.values() for j in names
        }
        missing = [j for j, i in self.actuator_ids.items() if i < 0]
        if missing:
            raise RuntimeError(f"robot.xml has no actuator for: {missing}")
        # Actuator ids in LEGS / joint order, so set_angles is one vectorized write.
        import numpy as np
        self.ctrl_idx = np.array([self.actuator_ids[j] for leg in LEGS for j in JOINT_NAMES[leg]])

        # Start already standing in the rest pose instead of dropping from zero angles.
        for leg in LEGS:
            for j, a in zip(JOINT_NAMES[leg], REST_POSE[leg]):
                jid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, j)
                self.data.qpos[self.model.jnt_qposadr[jid]] = a
                self.data.ctrl[self.actuator_ids[j]] = a
        mujoco.mj_forward(self.model, self.data)

        self.substeps = max(1, round(DT / self.model.opt.timestep))
        self.viewer = None
        if viewer:
            import mujoco.viewer
            self.viewer = mujoco.viewer.launch_passive(self.model, self.data)

    def set_angles(self, leg_angles: dict) -> None:
        """leg_angles must have all four legs."""
        self.data.ctrl[self.ctrl_idx] = [a for leg in LEGS for a in leg_angles[leg]]

    def advance(self) -> None:
        for _ in range(self.substeps):
            self.mj.mj_step(self.model, self.data)
        if self.viewer is not None and self.viewer.is_running():
            self.viewer.sync()

    def is_running(self) -> bool:
        return self.viewer is None or self.viewer.is_running()

    def close(self) -> None:
        if self.viewer is not None:
            self.viewer.close()


# -----------------------------------------------------------------------
# Hardware interface (PCA9685 via adafruit-circuitpython-servokit)
# -----------------------------------------------------------------------
class HardwareInterface:
    def __init__(self) -> None:
        from adafruit_servokit import ServoKit   # raises if not installed / no I2C
        self.kit = ServoKit(channels=16)
        # deg = (angle - lo) / (hi - lo) * 180, so each joint's range spans the servo's 0-180.
        self.map = {}
        for leg in LEGS:
            k = _LEG[leg]
            self.map[leg] = [
                (SERVO_CHANNELS[leg][i], k.lo[i], 180.0 / (k.hi[i] - k.lo[i]), SERVO_INVERT[leg][i])
                for i in range(3)
            ]
        # Last angle sent per channel. Each servo write is a separate I2C transaction,
        # so skipping unchanged servos is the main cost saving on the Pi.
        self.sent: dict[int, float] = {}
        print("PCA9685 ready. Keep hands clear: moving to rest pose...")
        self.set_angles(REST_POSE)
        time.sleep(2.0)

    def set_angles(self, leg_angles: dict) -> None:
        servo, sent = self.kit.servo, self.sent
        for leg, angles in leg_angles.items():
            for (ch, lo, scale, invert), a in zip(self.map[leg], angles):
                deg = _clamp((a - lo) * scale, 0.0, 180.0)
                if invert:
                    deg = 180.0 - deg
                last = sent.get(ch)
                if last is None or abs(deg - last) >= SERVO_DEADBAND:
                    servo[ch].angle = deg
                    sent[ch] = deg

    def advance(self) -> None:
        pass

    def is_running(self) -> bool:
        return True

    def close(self) -> None:
        # Stop sending pulses so the servos go limp instead of holding torque.
        for leg in LEGS:
            for ch in SERVO_CHANNELS[leg]:
                self.kit.servo[ch].angle = None
        self.sent.clear()


# -----------------------------------------------------------------------
# Keyboard input (pynput listens globally, not just in the viewer window)
# -----------------------------------------------------------------------
class KeyboardController:
    def __init__(self) -> None:
        self.cmd = Command()
        self.running = True
        self.lock = threading.Lock()
        try:
            from pynput import keyboard
        except ImportError:
            print("pynput not installed: no keyboard control, the robot will just stand.")
            return

        K = keyboard.Key
        shift = (K.shift, K.shift_l, K.shift_r)

        def on_press(key):
            with self.lock:
                c = self.cmd
                if key == K.up:          c.vx = KEY_VX
                elif key == K.down:      c.vx = -KEY_VX
                elif key == K.left:      c.yaw = KEY_YAW
                elif key == K.right:     c.yaw = -KEY_YAW
                elif key == K.space:     c.z_dir = -1.0
                elif key in shift:       c.z_dir = 1.0
                elif key == K.esc:       self.running = False
                else:
                    ch = (getattr(key, 'char', None) or '').lower()
                    if ch == 'r':
                        c.reset_z = True
                    elif ch == 'x':
                        c.estop = True
                        c.vx = c.yaw = c.z_dir = 0.0
                        print("\n[!] E-STOP: press C to clear")
                    elif ch == 'c' and c.estop:
                        c.estop = False
                        print("[i] E-stop cleared")

        def on_release(key):
            with self.lock:
                c = self.cmd
                if key in (K.up, K.down):
                    c.vx = 0.0
                elif key in (K.left, K.right):
                    c.yaw = 0.0
                elif key == K.space or key in shift:
                    c.z_dir = 0.0
                elif (getattr(key, 'char', None) or '').lower() == 'r':
                    c.reset_z = False

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()
        print("Controls: ARROWS walk/turn | SPACE/SHIFT lower/raise | R reset height | "
              "X e-stop | C clear | ESC quit")

    def get(self) -> tuple[Command, bool]:
        with self.lock:
            c = self.cmd
            return Command(c.vx, c.yaw, c.z_dir, c.reset_z, c.estop), self.running


# -----------------------------------------------------------------------
# Main loop
# -----------------------------------------------------------------------
def main(hardware: bool = False, demo_vx: float = 0.0) -> None:
    iface = HardwareInterface() if hardware else SimInterface()
    kb = KeyboardController()
    ctrl = Controller()
    print("System online.")

    next_tick = time.perf_counter()
    try:
        while iface.is_running():
            cmd, running = kb.get()
            if not running:
                break
            if demo_vx and not cmd.estop and cmd.vx == 0.0:
                cmd.vx = demo_vx
            iface.set_angles(ctrl.step(cmd))
            iface.advance()

            # Fixed-rate loop: sleep until the next deadline; if we fell behind, don't try to catch up.
            next_tick += DT
            spare = next_tick - time.perf_counter()
            if spare > 0.0:
                time.sleep(spare)
            else:
                next_tick = time.perf_counter()
    except KeyboardInterrupt:
        print("\nForce quit.")
    finally:
        if iface.is_running():
            print("Returning to rest pose...")
            for _ in range(100):
                iface.set_angles(ctrl.ease_to_rest())
                iface.advance()
                time.sleep(0.02)
        iface.close()
        print("Stopped. Safe to power off.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quadruped trot gait controller")
    parser.add_argument("--hardware", action="store_true",
                        help="drive the real robot through the PCA9685 (default: MuJoCo sim)")
    parser.add_argument("--vx", type=float, default=0.0,
                        help="walk forward at this fraction of full stride without pressing keys")
    args = parser.parse_args()
    main(hardware=args.hardware, demo_vx=args.vx)
