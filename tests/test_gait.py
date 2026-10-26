import itertools
import math
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "controller"))
import ik_controller as ic  # noqa: E402


# -----------------------------------------------------------------------
# Gait math (no MuJoCo needed)
# -----------------------------------------------------------------------
def test_limits_match_robot_xml():
    for names in ic.JOINT_NAMES.values():
        for j in names:
            lo, hi = ic.JOINT_LIMITS[j]
            assert lo < hi


def test_rest_pose_inside_limits():
    for leg in ic.LEGS:
        for j, a in zip(ic.JOINT_NAMES[leg], ic.REST_POSE[leg]):
            lo, hi = ic.JOINT_LIMITS[j]
            assert lo <= a <= hi, (j, a)


def test_zero_command_returns_rest_pose():
    gait = ic.TrotGait()
    for _ in range(100):
        angles = gait.get_joint_angles()
    for leg in ic.LEGS:
        assert angles[leg] == pytest.approx(ic.REST_POSE[leg])


@pytest.mark.parametrize("vx,yaw,z", list(itertools.product((-2, -1, 0, 0.5, 1, 2), (-2, -1, 0, 1, 2), (-0.4, 0, 0.4))))
def test_angles_stay_inside_limits(vx, yaw, z):
    gait = ic.TrotGait()
    for _ in range(200):
        angles = gait.get_joint_angles(vx, yaw, z)
        for leg in ic.LEGS:
            for j, a in zip(ic.JOINT_NAMES[leg], angles[leg]):
                lo, hi = ic.JOINT_LIMITS[j]
                assert lo <= a <= hi


def test_diagonal_pairs_alternate():
    gait = ic.TrotGait()
    gait.phase = math.pi / 2 - 2 * math.pi * ic.GAIT_FREQ * ic.DT   # next step lands on peak swing for FR+BL
    angles = gait.get_joint_angles(vx=1.0)
    for leg in ('FR', 'BL'):
        assert angles[leg][1] != pytest.approx(ic.REST_POSE[leg][1])   # lifted
    for leg in ('FL', 'BR'):
        assert angles[leg][1] == pytest.approx(ic.REST_POSE[leg][1])   # planted


def test_estop_holds_pose_and_phase():
    c = ic.Controller()
    for _ in range(50):
        c.step(ic.Command(vx=1.0))
    held = {leg: list(a) for leg, a in c.angles.items()}
    phase = c.gait.phase
    for _ in range(50):
        c.step(ic.Command(vx=1.0, estop=True))
    assert c.angles == held
    assert c.gait.phase == phase
    assert c.vx.current == 0.0


def test_height_is_clamped_and_resets():
    c = ic.Controller()
    for _ in range(1000):
        c.step(ic.Command(z_dir=1.0))
    assert c.z == ic.Z_LIMIT
    for _ in range(1000):
        c.step(ic.Command(reset_z=True))
    assert abs(c.z) < 1e-3


def test_ramp_limits_rate():
    r = ic.VelocityRamp(rate=2.0)
    assert r.update(1.0, 0.1) == pytest.approx(0.2)
    for _ in range(10):
        r.update(1.0, 0.1)
    assert r.current == 1.0


# -----------------------------------------------------------------------
# Hardware mapping, against a fake PCA9685 (no Pi needed)
# -----------------------------------------------------------------------
@pytest.fixture
def hw(monkeypatch):
    writes = []

    class Servo:
        def __init__(self, ch):
            self.ch = ch

        @property
        def angle(self):
            raise AssertionError("controller should not read servo angles")

        @angle.setter
        def angle(self, deg):
            writes.append((self.ch, deg))

    class ServoKit:
        def __init__(self, channels):
            self.servo = [Servo(ch) for ch in range(channels)]

    monkeypatch.setitem(sys.modules, "adafruit_servokit", types.SimpleNamespace(ServoKit=ServoKit))
    monkeypatch.setattr(ic.time, "sleep", lambda s: None)
    iface = ic.HardwareInterface()
    return iface, writes


def test_hardware_maps_into_servo_range(hw):
    iface, writes = hw
    assert len(writes) == 12                      # rest pose sent once at startup
    assert all(0.0 <= deg <= 180.0 for _, deg in writes)
    c = ic.Controller()
    for _ in range(300):
        iface.set_angles(c.step(ic.Command(vx=1.0, yaw=0.5)))
    assert all(0.0 <= deg <= 180.0 for _, deg in writes)


def test_hardware_skips_unchanged_servos(hw):
    iface, writes = hw
    writes.clear()
    c = ic.Controller()
    for _ in range(100):                          # standing still: nothing to send
        iface.set_angles(c.step(ic.Command()))
    assert writes == []
    for _ in range(100):                          # walking: servos get updated
        iface.set_angles(c.step(ic.Command(vx=1.0)))
    assert {ch for ch, _ in writes} == {ch for chs in ic.SERVO_CHANNELS.values() for ch in chs}


def test_hardware_close_releases_servos(hw):
    iface, writes = hw
    writes.clear()
    iface.close()
    assert sorted(writes) == sorted((ch, None) for chs in ic.SERVO_CHANNELS.values() for ch in chs)
    writes.clear()
    iface.set_angles(ic.REST_POSE)                # cache was reset, so everything is re-sent
    assert len(writes) == 12


# -----------------------------------------------------------------------
# Headless MuJoCo smoke tests
# -----------------------------------------------------------------------
@pytest.fixture
def sim():
    pytest.importorskip("mujoco")
    return ic.SimInterface(viewer=False)


def _simulate(sim, cmd: ic.Command, seconds: float):
    c = ic.Controller()
    m, d = sim.model, sim.data
    base = m.body('base_link').id
    for _ in range(int(1.0 / ic.DT)):            # settle
        sim.set_angles(c.step(ic.Command()))
        sim.advance()
    start = d.xpos[base].copy()
    min_up, turned, prev = 1.0, 0.0, 0.0
    for _ in range(int(seconds / ic.DT)):
        sim.set_angles(c.step(cmd))
        sim.advance()
        R = d.xmat[base].reshape(3, 3)
        min_up = min(min_up, R[2, 2])
        heading = math.atan2(R[1, 0], R[0, 0])
        turned += (heading - prev + math.pi) % (2 * math.pi) - math.pi
        prev = heading
    return d.xpos[base] - start, d.xpos[base][2], min_up, math.degrees(turned)


def test_stands_on_feet(sim):
    c = ic.Controller()
    for _ in range(200):
        sim.set_angles(c.step(ic.Command()))
        sim.advance()
    m, d = sim.model, sim.data
    touching = {m.body(m.geom_bodyid[g]).name
                for con in d.contact[:d.ncon] for g in (con.geom1, con.geom2) if m.geom_bodyid[g]}
    assert touching == {'fr_end', 'br_end', 'fl_end', 'bl_end'}
    assert d.xpos[m.body('base_link').id][2] > 0.12


def test_walks_forward(sim):
    moved, z, min_up, turned = _simulate(sim, ic.Command(vx=1.0), 5.0)
    assert moved[0] > 0.3
    assert abs(turned) < 20
    assert min_up > 0.9 and z > 0.12


def test_walks_backward(sim):
    moved, _, min_up, _ = _simulate(sim, ic.Command(vx=-1.0), 5.0)
    assert moved[0] < -0.3
    assert min_up > 0.9


@pytest.mark.parametrize("yaw,sign", [(1.0, 1), (-1.0, -1)])
def test_turns_in_commanded_direction(sim, yaw, sign):
    _, _, min_up, turned = _simulate(sim, ic.Command(yaw=yaw), 5.0)
    assert sign * turned > 60
    assert min_up > 0.85
