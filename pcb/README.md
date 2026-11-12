# Quadruped PCB

My first PCB: a 99 × 79 mm carrier board that sits on top of the robot and ties everything together. A 2S LiPo plugs in, the Raspberry Pi Zero 2 W plugs on top, and all 12 servos plug in at the corners.

**Status:** designed in KiCad 10, fully routed and DRC clean. Not ordered yet. Next up is the silkscreen and labelling pass to make it look as good as it works.

Open `quadped.kicad_pro` in KiCad 10 or newer.

---

## What it does

1. **Takes battery power safely:** fuse, reverse-polarity protection and a battery monitor.
2. **Makes two separate 5 V supplies:** one for the servos, one for the Pi, so servo current spikes can't reset the Pi.
3. **Connects the Pi to the servos:** the Pi talks I2C to a PCA9685, which drives the 12 servo signals.

The controller code doesn't change: the PCA9685 is at I2C address `0x40`, same as the Adafruit breakout `ServoKit` already expects.

```
                         ┌──► U2 buck 5 V / 5 A ───► +5V_SERVO ──► 12 servos
 2S LiPo ─► J1 ─► F1 ─► Q1 ─► R2 shunt ─┤
 7.4 V      XT30  7.5 A  reverse  │      └──► U3 buck 5 V / 2.5 A ─► +5V_PI ──► Pi Zero 2 W
                         polarity │                                            │ 3.3 V
                                  U1 INA219 ◄──────── I2C ─────────────────────┤
                                  (0x41)              U4 PCA9685 (0x40) ◄──────┤
                                                      └─► 12 servo signals     │
                                                      J3 Qwiic port ◄──────────┘
```

---

## The circuit

### 1. Battery input

| Part | Does |
|---|---|
| **J1** XT30 | Battery plug. Pin 2 is +. |
| **F1** 7.5 A mini blade fuse | Blows on a short instead of the LiPo. Walking draws 2–4 A, so it won't trip in normal use. |
| **Q1** AOD4185 P-MOSFET | Reverse-polarity protection. Battery the right way: fully on, almost no loss. Backwards: off, nothing gets power. Wastes far less than a diode would at 5 A. |
| **R1** 10 kΩ | Pulls Q1's gate to ground, which is what turns it on. |

Output: `VBAT` (6.6–8.4 V).

### 2. Battery monitor

| Part | Does |
|---|---|
| **R2** 0.01 Ω shunt | All battery current flows through it. At 5 A it drops just 0.05 V. |
| **U1** INA219 | Reads the voltage across R2 (current) and the battery voltage, and reports both over I2C. Lets the Pi stop before the LiPo drains below a safe level. |
| **C1** 100 nF | Decoupling for U1. |

**I2C address:** the INA219 has 16 built-in addresses (0x40–0x4F), picked by how its A0 and A1 pins are wired. Both on GND would give 0x40 and clash with the PCA9685, so A0 goes to 3.3 V for **0x41**.

Output: `VBAT_SENSE`, which feeds both regulators.

### 3. Power rails

| Part | Does |
|---|---|
| **U2** 5 V / 5 A buck module | Servo supply (`+5V_SERVO`). |
| **U3** 5 V / 2.5 A buck module | Pi supply (`+5V_PI`). Separate so servo noise can't reach the Pi. |
| **C2** 100 µF | Input reserve next to both bucks. |
| **C3, C4** 1000 µF | Servo reserve, one by the front servos and one by the back. They supply current bursts faster than the buck can react. |
| **D1, D2** + **R3, R4** | Power LEDs for each rail. |

Bucks are ready-made modules (e.g. Pololu D24V50F5 / D24V22F5) on header pins, so no switching-regulator layout to get wrong. The footprints are 3-pin placeholders until the exact modules are picked.

### 4. Pi, servo driver and servos

| Part | Does |
|---|---|
| **J2** 2×20 header | The Pi plugs in here. 5 V in on pins 2/4, 3.3 V out on pin 1, I2C on pins 3/5, servo enable on pin 11 (GPIO17). |
| **U4** PCA9685 | Turns I2C commands into 16 PWM outputs (12 used). Runs on 3.3 V to match the Pi. Address 0x40. |
| **C5, C6** | Decoupling for U4. |
| **R5** 10 kΩ + **JP1** | R5 holds U4's output-enable off at boot so the servos don't twitch before the code runs; GPIO17 turns them on. Bridge JP1 to skip that and keep outputs always on. |
| **R6–R17** 220 Ω | One per servo signal. Protects U4 if a servo wire shorts. |
| **J15–J26** | Servo plugs, three per corner. Signal / 5 V / GND, GND toward the board edge. |
| **J3** Qwiic | Spare I2C port for an IMU later. |
| **R18, R19** | Spare I2C pull-up pads, not fitted (the Pi has its own). |
| **TP1–TP5** | Test points: VBAT, 5 V servo, 5 V Pi, 3.3 V, GND. |

**Servo channels** match `SERVO_CHANNELS` in the controller:

| Leg | Headers | Channels |
|---|---|---|
| FR | J15–J17 | 0–2 |
| BR | J18–J20 | 3–5 |
| FL | J21–J23 | 6–8 |
| BL | J24–J26 | 9–11 |

Each leg's three headers are hip, mid, end, in that order.

---

## The board

- **99 × 79 mm, 2 layers.** Mounted on top of the robot with the battery underneath. Front is along the 99 mm length.
- **Layout:** power runs up the left in battery order. The Pi sits lengthwise on the right with its camera end forward. Servo headers sit at the four corners, nearest their legs. Only flat parts go under the Pi.
- **Tracks:** power nets are 1.5 mm, signals 0.15–0.2 mm. Ground is a copper fill on both layers, stitched together with vias.
- **Mounting:** 4× M3 at the corners, 4× M2.5 for the Pi.

```
                 FRONT
   ┌──────────── 79 mm ────────────┐
   │ [FL servos]       [FR servos] │
   │       C3                      │
   │                ┌── camera ──┐ │
   │  U2  U3        │            │ │
   │                │  Pi Zero   │ │ 99 mm
   │  R2  U1        │  (U4 and   │ │
   │                │  R6–R17    │ │
   │  Q1            │  under it) │ │
   │  F1            └──── SD ────┘ │
   │        J1 XT30   C4           │
   │ [BL servos]       [BR servos] │
   └───────────────────────────────┘
                 BACK
```

### Worth knowing

- **J2 uses a `PinHeader_2x20` footprint**, with a female socket soldered into it. KiCad's `PinSocket` footprints are mirrored for boards that face each other, which would swap the Pi's 5 V and GND pins here.
- **The XT30 opening faces the board edge**, with the pins on the inside.
- **DRC exclusions:** servo header courtyards overlap because they sit side by side at 2.54 mm on purpose.

---

## Ordering (when it's time)

1. File → Fabrication Outputs → **Gerbers** (F/B.Cu, F/B.Silkscreen, F/B.Mask, Edge.Cuts) and **Drill Files** into one folder. Zip it.
2. Upload to JLCPCB or PCBWay: 2 layers, 1.6 mm, 1 oz copper, HASL lead-free.
3. Optional: have the factory assemble U1 and U4 (fine-pitch chips) using the BOM and position files.
4. Buy separately: XT30 male (PW), Keystone 3568 fuse holder + 7.5 A fuse, 2×20 female socket, 12× 1×3 headers, the three electrolytic caps, both buck modules.

**First power-up:** check for shorts with a multimeter first. Then power it from a current-limited bench supply with no Pi and no servos, and check both rails read about 5 V. Then add the Pi (`i2cdetect -y 1` should show 40, 41 and 70), then one servo, then all 12.
