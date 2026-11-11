# Quadruped PCB

A custom board to replace the rats' nest of wires between the battery, the Pi, the PCA9685 breakout and the 12 servos. Designed in KiCad.

**Status:** schematic in progress (KiCad 10). See the [component list](#component-list) for every part.

---

## TL;DR

One board, about the size of the robot's back, that:

1. takes a **2S LiPo** (7.4 V) in through a fuse and reverse-polarity protection,
2. makes **two separate 5 V rails**: a big one (5 A+) for the servos and a small clean one (2.5 A) for the Pi,
3. has the **PCA9685 chip** on it (instead of the Adafruit breakout), talking to the Pi over I2C,
4. has **12 servo headers** (3-pin each),
5. has a **2x20 header** the Pi Zero 2 W plugs into, upside down or on standoffs,
6. measures **battery voltage and current** so the Pi knows when the LiPo is getting low,
7. has a spare **I2C connector** for an IMU later (for the CV / balance stuff).

The controller code doesn't change: the PCA9685 is still at I2C address `0x40`, which is what `ServoKit` already looks for.

---

## How it works

### The big picture

The board does three jobs:

1. **Takes battery power safely.** A fuse, protection against plugging the battery in backwards, and a battery meter.
2. **Turns it into two clean 5 V supplies.** One for the 12 servos, one for the Pi.
3. **Connects the Pi to the servos.** The Pi sends commands over two I2C wires to a servo driver chip, which makes the 12 control signals.

Power flows like this:

```
Battery → J1 → F1 → Q1 → R2 (shunt) → U2 → servos
                                     → U3 → Pi → 3.3 V → U1, U4, J3
```

Signals flow like this:

```
Pi (I2C wires) → U4 (servo driver) → 12 servo signal pins
               → U1 (battery meter)
               → J3 (spare port)
```

### Section 1: Battery input

**Job:** get battery power onto the board without fires or fried parts.

| Part | What it does |
|---|---|
| **J1** XT30 connector | Where the battery plugs in. Pin 1 is +, pin 2 is −. |
| **F1** 7.5 A fuse | If anything shorts, the fuse blows instead of the LiPo dumping 50 A+ into the board and catching fire. Normal walking only draws 2–4 A, so 7.5 A won't blow by accident. |
| **Q1** AOD4185 P-MOSFET (DPAK) | An electronic switch. Battery plugged in the right way, it turns fully on and wastes almost no power. Plugged in backwards, it stays off and nothing gets power. A plain diode would also protect, but would waste about 2.5 W as heat at 5 A. Drain (pin 2) faces the battery, source (pin 3) faces VBAT. |
| **R1** 10 kΩ | Holds Q1's gate at ground. Ground being about 7 V below the battery voltage is exactly what turns a P-MOSFET on. |
| **PWR_FLAGs** | Not real parts. They tell KiCad's checker "power comes in here" so it doesn't flag VBAT and GND as having no power source. |

**Output:** `VBAT` (6.6–8.4 V), protected battery power.

### Section 2: Battery monitor

**Job:** let the Pi read battery voltage and current, so you never drain the LiPo too far. A LiPo drained below about 6.0 V (for 2 cells) is permanently damaged, and the Pi can't measure voltage on its own.

| Part | What it does |
|---|---|
| **R2** 0.01 Ω shunt | A tiny resistor that all the battery current flows through. At 5 A it drops only 0.05 V, which is small enough to ignore but big enough to measure. |
| **U1** INA219 | Measures the small voltage across R2 to get current, and also measures the battery voltage itself. Sends both to the Pi over I2C. Its address pins are set for **0x41**, because the servo driver already uses 0x40. |
| **C1** 100 nF | Decoupling capacitor: a small local energy store right at U1's power pin that smooths out tiny electrical noise. Every chip gets one. |

**Output:** `VBAT_SENSE`, the same power as VBAT after passing through the shunt.

**What "address 0x41" means.** Every I2C chip shares the same two wires (SDA, SCL). The Pi starts each message with an address, and only the chip with that address answers. `0x` just means hexadecimal: 0x40 = 64, 0x41 = 65. They're ID numbers.

The INA219 has 16 address configurations built in, 0x40 to 0x4F. You choose one with wiring: A0 and A1 can each go to GND, 3.3 V, SDA or SCL, and each combination maps to one address. At power-up the chip checks those two pins and uses the matching address. The wiring doesn't create the address; it picks one of the 16 the chip already has:

| A1 | A0 | Address |
|---|---|---|
| GND | GND | 0x40 (clashes with the PCA9685) |
| GND | 3.3 V | **0x41** (what we use) |

If both chips were at 0x40, they'd answer the same messages at once and garble each other. 0x41 is just the smallest change from the default. The PCA9685 has all six of its address pins on GND, which gives 0x40, the address the code expects.

### Section 3: Power rails

**Job:** turn 7.4 V into 5 V for the servos and, separately, 5 V for the Pi.

**Why two separate supplies?** When 12 servos move at once they pull big current spikes, and the voltage dips. If the Pi shared that supply, it would reset mid-step.

| Part | What it does |
|---|---|
| **U2** 5 V / 5 A buck module | Powers the servos. A "buck" steps voltage down at about 90 % efficiency. A simple linear regulator would turn about 15 W into heat instead. It's a ready-made module, so you don't have to design the tricky circuit yourself. |
| **U3** 5 V / 2.5 A buck module | Powers the Pi. It's a separate module so servo noise can't reach the Pi. |
| **C2** 100 µF | Sits on the battery line next to both modules. The battery wire is long and can't deliver sudden current quickly, so this capacitor covers the gap. |
| **C3** 1000 µF (front) | Reserve for the front servos. When servos suddenly pull current, this capacitor supplies the burst faster than U2 can react. |
| **C4** 1000 µF (back) | The same for the back servos. |
| **D1 + R3** LED + 1 kΩ | Lights when the servo supply is on. R3 limits the current so the LED doesn't burn out. |
| **D2 + R4** LED + 1 kΩ | Lights when the Pi supply is on. |

**Outputs:** `+5V_SERVO` and `+5V_PI`.

### Section 4: Pi, servo driver, servos, extras

**Job:** the brains-to-muscles connection.

| Part | What it does |
|---|---|
| **J2** 2×20 header | The Pi plugs in here. Pins 2/4 feed it 5 V from U3. Pin 1 gives back 3.3 V to power the chips. Pins 3/5 are the I2C wires (SDA/SCL). Pin 11 (GPIO17) controls the servo enable. |
| **U4** PCA9685 | Servo driver chip, the same one on the Adafruit breakout. The Pi sends "servo 4 to 90°" over I2C, and U4 generates the timed pulse that servos understand, on 16 outputs (we use 12). Runs on 3.3 V so its signals match the Pi's. Address 0x40, which is what the code already uses. |
| **C5** 100 nF | Decoupling for U4. |
| **C6** 10 µF | Extra smoothing on U4's 3.3 V supply. |
| **R5** 10 kΩ | Safety pull-up on U4's OE (output enable) pin. At power-on, before the code runs, it keeps all servo outputs off, so the robot doesn't twitch at boot. The code then sets GPIO17 low to turn the outputs on. |
| **JP1** solder jumper | Bridge it with solder to permanently enable the outputs and skip the GPIO17 feature. A backup option. |
| **R6–R17** 220 Ω ×12 | One per servo signal wire. If a servo wire gets crushed and shorts, this resistor limits the current so U4 survives. |
| **R18, R19** 4.7 kΩ (not fitted) | Spare pads for I2C pull-up resistors. The Pi already has them built in, so these stay empty unless I2C misbehaves. |
| **J15–J26** 3-pin headers ×12 | Servo plugs: signal / 5 V / GND. Three per corner, matching the code's channels (FR = 0–2, BR = 3–5, FL = 6–8, BL = 9–11). |
| **J3** Qwiic connector | Spare 4-pin I2C port. Plug in an IMU later for balance and CV, no soldering needed. |
| **TP1–TP5** test points | Labelled spots to touch multimeter probes: VBAT, servo 5 V, Pi 5 V, 3.3 V, GND. |
| **H1–H4** M3 holes | Screw the board to the robot body. |
| **H5–H8** M2.5 holes | Standoffs to hold the Pi. |

The [component list](#component-list) further down has the KiCad symbol and exact value for every part, plus the servo channel map and net names.

---

## Wait, what's a PCB

A printed circuit board is just wires made of copper, glued to a fiberglass sheet. Instead of running jumper wires from pin to pin, you draw where the copper goes, send the files to a factory (JLCPCB, PCBWay, OSH Park...), and a week or two later you get boards back for a few bucks each.

Words you'll see a lot:

| Word | Meaning |
|---|---|
| **Schematic** | The circuit diagram. *What* connects to *what*. No physical sizes, just logic. |
| **Symbol** | A part's drawing in the schematic (a box with pins). |
| **Footprint** | A part's physical copper pads on the board. One symbol can have many footprints (same resistor, different sizes). |
| **Net** | One electrical connection. "GND" is a net; everything on it is connected. |
| **Trace** | A copper wire on the board. |
| **Via** | A little plated hole that connects a trace on the top layer to the bottom layer. |
| **Pour / zone** | A big filled area of copper, usually GND. Good for current and noise. |
| **Layer** | Copper sheets. A 2-layer board has copper on top and bottom. That's all we need. |
| **Silkscreen** | The white text/labels printed on the board. |
| **THT / SMD** | Through-hole parts (legs go through holes, easy to solder) vs surface-mount (sit on pads, tiny, usually assembled by the factory). |
| **Decoupling cap** | A small capacitor (usually 100 nF) right next to a chip's power pin. Smooths out tiny spikes. Every chip gets one. |
| **ERC / DRC** | Electrical Rules Check (schematic sanity check) / Design Rules Check (board sanity check: traces too close, etc). Run both. Always. |
| **Gerbers** | The files you send to the factory. One per layer. |
| **BOM** | Bill of materials: the shopping list. |

---

## The circuit

### Block diagram

```
                       ┌───────────────────────── servo rail (5 V, 5 A+) ─────────┐
                       │                                                          │
 2S LiPo ──XT30──► FUSE ──► REVERSE ──► INA219 ──┬──► BUCK #1 (5 V / 5 A) ──► big cap ──► 12x servo V+
 7.4 V            (7.5 A)   PROTECTION   shunt   │
 (6.6–8.4 V)                (P-MOSFET)           └──► BUCK #2 (5 V / 2.5 A) ──► Pi 5 V (pins 2, 4)
                                                                                │
                                                                         Pi 3.3 V (pin 1)
                                                                                │
                                     ┌──────────────────────────────────────────┤
                                     ▼                                          ▼
 Pi GPIO2/3 (I2C) ═══════════► PCA9685 (0x40) ──16 PWM──► 12x servo signal     INA219 (0x41)
                  ║            OE ◄── Pi GPIO17                                  │
                  ╚═══════════► Qwiic/STEMMA connector (spare: IMU later)        │
                  ╚══════════════════════════════════════════════════════════════╝
```

All grounds are connected (one GND net), but see the layout tips about *where* they join.

### 1. Battery input

**What:** XT30 connector → fuse → reverse-polarity protection.

- **Battery:** 2S LiPo, 7.4 V nominal (8.4 V full, ~6.6 V empty), 1500–2200 mAh is a decent start. XT30 connector (rated ~15 A, small).
- **Fuse:** a blade fuse holder (mini/ATM) with a 7.5 A fuse. If something shorts, the fuse dies instead of the battery catching fire. LiPos can dump 50 A+ into a short. Don't skip this.
- **Reverse-polarity protection:** a P-channel MOSFET wired as an "ideal diode". If you plug the battery in backwards, the MOSFET stays off and nothing gets hurt. A normal diode would also work but wastes ~2.5 W as heat at 5 A; the MOSFET wastes a few tens of mW. Pick one rated for **−20 V or −30 V, >10 A, low R<sub>DS(on)</sub>** (e.g. AOD4185 or similar, TO-252). Gate goes to GND through a ~10 kΩ resistor. Google "P-channel MOSFET reverse polarity protection", it's a 2-part circuit.
- **Power switch:** easiest is an inline switch rated ≥10 A on the battery lead (off-board), or just unplug the battery.

### 2. Battery monitor (INA219)

LiPos are permanently damaged if you run them below ~3.0 V per cell (6.0 V for 2S). The Pi has no analog input, so it can't read voltage on its own. An **INA219** fixes that: it sits on the same I2C bus and reports bus voltage and current (through a tiny shunt resistor, e.g. 0.01 Ω).

- **Address clash!** The INA219 defaults to `0x40`, same as the PCA9685. Tie its **A0 pin to VS (3.3 V)** to move it to `0x41`.
- Shunt: 0.01 Ω, 2512 size, 1 W or more. Max readable current at 0.01 Ω is ~32 A, way more than we need, so resolution is fine.
- Later: have the controller sit down and stop when the battery reads below ~6.8 V.

This block is optional for v1, but highly recommended.

### 3. Power: two 5 V rails

**Why two?** Servos are loud electrically. When 12 of them all move at once, they pull big current spikes and the voltage dips. If the Pi shares that rail, it browns out and reboots mid-step. So: one regulator for servos, one for the Pi, joined only at ground.

**Why a "buck"?** A buck converter steps voltage down efficiently (~90 %). A linear regulator (like a 7805) would turn the extra 3 V × 5 A = 15 W into heat. Nope.

**How much current?** MG90S: ~100–250 mA moving, ~700 mA+ stalled (pushing against something). 12 of them:
- typical walking: 2–4 A,
- worst case (all straining): ~9 A.

So the servo rail should handle **5 A continuous** and survive spikes, with a big capacitor to soak up the bursts.

**Recommendation for v1: use pre-made buck modules**, soldered onto the board through header pins. Designing a 5 A switching regulator from scratch is the single hardest part of this board (layout really matters, it's easy to get wrong). Modules are tested and cheap.

| Rail | Module (example, check the datasheet) | Notes |
|---|---|---|
| Servo 5 V | Pololu **D24V50F5** (5 V, 5 A) or similar | Add two 1000 µF, 16 V low-ESR electrolytic caps on its output: one by the front servo headers, one by the back. |
| Pi 5 V | Pololu **D24V22F5** (5 V, 2.5 A) or similar | Feeds the Pi's 5 V pins directly. |

In KiCad you just make a custom footprint for each module (a few header holes at the right spacing, read off the module's datasheet drawing).

> MG90S is rated 4.8–6 V. 6 V gives more torque, but a 2S LiPo near empty (6.6 V) leaves very little headroom for a 6 V regulator. 5 V is the safe choice for v1.

v2 idea: once v1 works, swap the modules for chips-down buck regulators using a manufacturer's reference layout.

### 4. Raspberry Pi Zero 2 W

The Pi plugs into a **2x20 female header** on the board. We only use a few pins:

| Pi pin | Name | Goes to |
|---|---|---|
| 2, 4 | 5 V | Pi buck output (powers the Pi *through the header*) |
| 6, 9, 14, ... | GND | GND |
| 1 | 3.3 V | PCA9685 VDD, INA219 VS, Qwiic 3.3 V |
| 3 | GPIO2 / SDA | I2C data |
| 5 | GPIO3 / SCL | I2C clock |
| 11 | GPIO17 | PCA9685 OE (output enable) |

Notes:
- Powering through the 5 V pins skips the Pi's own little fuse. That's normal for robot boards, just don't also plug a USB power supply into the Pi while the battery is connected.
- Pi Zero is 65 × 30 mm with M2.5 holes on a 58 × 23 mm rectangle. Put matching mounting holes on the PCB so it can sit on standoffs.
- The Pi already has 1.8 kΩ pull-up resistors on SDA/SCL, so we don't strictly need more. Add footprints for 4.7 kΩ pull-ups anyway and leave them unpopulated ("DNP") in case.

### 5. PCA9685 servo driver

This is the same chip that's on the Adafruit breakout. It takes I2C commands and generates 16 PWM signals (we use 12).

| PCA9685 pin | Connect to | Why |
|---|---|---|
| VDD | 3.3 V (from Pi) + 100 nF + 10 µF to GND | Runs at 3.3 V so the I2C matches the Pi. No level shifter needed. |
| VSS | GND | |
| SDA, SCL | Pi GPIO2, GPIO3 | I2C |
| A0–A5 | GND | Address = `0x40` (what `ServoKit` expects) |
| EXTCLK | GND | Use the internal oscillator |
| OE (active low) | Pi GPIO17 + 10 kΩ pull-up to 3.3 V | **Safety:** at boot, the pull-up keeps all servo outputs *off* until the code pulls OE low. Add a solder jumper to GND to bypass it. |
| LED0–LED11 | 220 Ω resistor → servo header signal pins | Series resistor protects the chip if a servo wire shorts. |
| LED12–LED15 | Spare header or leave unconnected | Future use (LEDs, a 13th servo...) |

The PWM signal is 3.3 V. MG90S servos accept that fine.

> If you keep the OE feature, the controller needs a tiny change: set GPIO17 low after `ServoKit` starts (and high on shutdown to make the servos go limp). Or close the solder jumper and skip it.

### 6. Servo headers

12 × 3-pin 2.54 mm male headers (or one 3×12 block). Standard servo order, matching the MG90S wire colors:

```
 [ S ]  signal  orange  ← PCA9685 via 220 Ω
 [ + ]  5 V     red     ← servo rail
 [ - ]  GND     brown
```

Number them on the silkscreen to match `SERVO_CHANNELS` in the controller (channels 0–11: FR hip/mid/end, BR, FL, BL) and print the leg names next to them. Future you will be grateful.

### 7. Extras (cheap, worth it)

- **Qwiic / STEMMA QT connector** (4-pin JST-SH: GND, 3.3 V, SDA, SCL): plug an IMU (BNO085, MPU-6050 breakout...) in later without soldering.
- **Power LED** on each rail (LED + 1 kΩ). Instant "is it on" check.
- **Test points** on battery, servo 5 V, Pi 5 V, 3.3 V, GND. Makes probing with a multimeter easy.
- **Mounting holes** that match the body in the Fusion design.

---

## The steps

### 0. Install + learn the tool (an evening)

1. Install **KiCad 9 or newer** from kicad.org.
2. Do the official **Getting Started in KiCad** tutorial (docs.kicad.org). It walks through a whole tiny board from schematic to Gerbers. Seriously do this first; everything below will make sense after it.

### 1. Plan the physical size (in Fusion)

Open `cad/quadruped-v2-may-2026.f3z` and measure the space where the PCA9685 board and Pi currently sit. That's your board outline and mounting-hole positions. Write them down.

### 2. Schematic (most of the thinking happens here)

1. In KiCad: File → New Project → save it here in `pcb/` (e.g. `pcb/quadruped-board/`).
2. Open the **Schematic Editor**. Draw it in sections, one block from the circuit above at a time: power input → INA219 → regulators → Pi header → PCA9685 → servo headers → extras.
3. Use **net labels** (e.g. `SDA`, `SCL`, `+5V_SERVO`, `+5V_PI`, `+3V3`) instead of drawing long wires across the page. Same label = connected.
4. Most symbols exist already (search "PCA9685", "INA219", "Conn_02x20", "Conn_01x03"). For the buck modules, make a simple custom symbol.
5. Run **ERC** (Inspect → Electrical Rules Checker). Fix everything. "Power pin not driven" errors usually just need a `PWR_FLAG` symbol on that net.

### 3. Footprints

Tools → Assign Footprints. Pick sizes you can live with:
- Resistors/caps: **0805** if hand-soldering (big enough to handle), 0603 if the factory assembles.
- PCA9685: TSSOP-28 (`PCA9685PW`). Fine pitch. Either get the factory to assemble it (recommended) or hand-solder with lots of flux.
- Headers, XT30, fuse holder, big cap: through-hole. Easy to solder yourself.

### 4. Layout (the fun part)

1. Open the **PCB Editor** → Tools → Update PCB from Schematic. All parts appear in a pile with thin lines ("ratsnest") showing what connects.
2. Draw the board outline on the **Edge.Cuts** layer using your measurements from step 1.
3. Place parts first, route later. Placement is 80 % of the job:
   - Battery input, fuse, MOSFET, bucks along one edge, close together.
   - Big servo cap right next to the servo headers.
   - Servo headers along the edges, grouped by leg, so wires don't cross the body.
   - PCA9685 near the servo headers, Pi header wherever the Pi physically fits.
   - Decoupling caps *right next to* the chip pins they serve.
4. Route:
   - **High-current paths** (battery → fuse → MOSFET → bucks → servo headers): fat. Use copper zones/pours or traces **≥ 3 mm wide** on 1 oz copper. Or order 2 oz copper.
   - Signal traces (I2C, PWM): 0.25 mm is fine.
   - **Bottom layer = one big GND pour.** Top layer gets a GND pour too in empty space, stitched to the bottom with vias.
   - Keep the servo current's path to ground short and away from the I2C lines and the Pi.
5. Set the design rules to your factory's capabilities (JLCPCB and PCBWay publish them; a 0.2 mm min trace/space is a safe default), then run **DRC** until it's clean.
6. View → 3D Viewer to sanity-check. File → Export → STEP, then import into Fusion to make sure it actually fits in the body and the connectors aren't hitting anything.

### 5. Order

1. File → Fabrication Outputs → Gerbers + Drill files. Zip them.
2. Upload to JLCPCB / PCBWay. 2 layers, 1.6 mm, 5 boards is the cheap default.
3. If you want the SMD parts assembled (recommended for the PCA9685 and INA219), also export the BOM and the position file (CPL) and pick parts from their stock list.
4. Buy the through-hole stuff (headers, XT30, fuse holder, caps, buck modules) separately.

### 6. Bring-up (don't skip, don't rush)

Do this in order, and stop at the first thing that's wrong:

1. **Before power:** multimeter in continuity mode. Battery + to GND should *not* beep. Each rail to GND should not beep.
2. **First power:** no Pi, no servos. Ideally from a bench supply at 7.4 V with the current limit at ~200 mA (no LiPo yet). Check: LEDs on, servo rail ≈ 5 V, Pi rail ≈ 5 V.
3. **Reverse test** (bench supply only, current-limited): plug it in backwards, nothing should happen.
4. **Add the Pi.** It should boot. `i2cdetect -y 1` should show `40` (PCA9685), `41` (INA219) and `70` (the PCA9685's "all call" address, normal).
5. **One servo** on channel 0. Run the controller with `--hardware`, see it move.
6. **All 12 servos**, robot held in the air. Then the `SERVO_INVERT` calibration from the main README.
7. Then the LiPo. Then the floor.

---

## Component list

Every part on the board, with the reference name (what KiCad calls it) and what it does. Values in **bold** are what you type into KiCad.

### Section 1: Battery input

| Ref | Part | KiCad symbol | What it does |
|---|---|---|---|
| J1 | XT30 male, PCB mount | `Conn_01x02` | Battery plug. Pin 1 = +, pin 2 = −. On the back edge, lead comes up from the battery underneath. |
| F1 | Mini blade fuse holder + **7.5A** fuse | `Fuse` | Blows if something shorts, so the LiPo doesn't dump 50 A+ into the board. |
| Q1 | P-MOSFET, −20/−40 V, >10 A, TO-252 (**AOD4185**) | `Q_PMOS_GDS` | Reverse-polarity protection. Battery backwards = MOSFET stays off = nothing gets hurt. Drain toward the battery, source toward the load. |
| R1 | **10k**, 0805 | `R` | Pulls Q1's gate to GND so it turns on when the battery is the right way round. |

### Section 2: Battery monitor

| Ref | Part | KiCad symbol | What it does |
|---|---|---|---|
| U1 | INA219 (SOT-23-8) | search `INA219` | Measures battery voltage and current over I2C, so the Pi knows when the LiPo is low. A0 → 3.3 V, A1 → GND gives address **0x41** (the PCA9685 has 0x40). |
| R2 | **0.01Ω** shunt, 2512, ≥1 W | `R` | Tiny resistor all the battery current flows through. The INA219 measures the voltage across it to get the current. |
| C1 | **100nF**, 0805 | `C` | Decoupling for U1. |

### Section 3: Power rails

| Ref | Part | KiCad symbol | What it does |
|---|---|---|---|
| U2 | 5 V / 5 A buck module (e.g. Pololu D24V50F5) | custom (header pins) | Servo rail. Steps 7.4 V down to 5 V for the 12 servos. |
| U3 | 5 V / 2.5 A buck module (e.g. Pololu D24V22F5) | custom (header pins) | Pi rail. Separate from the servos so servo current spikes can't reset the Pi. |
| C2 | **100µF** 16 V electrolytic | `CP` | Input cap on VBAT next to the bucks. Steadies the battery voltage the modules see. |
| C3 | **1000µF** 16 V low-ESR electrolytic | `CP` | Servo rail reserve, front (near FL/FR headers). Supplies current bursts faster than the buck can react. |
| C4 | **1000µF** 16 V low-ESR electrolytic | `CP` | Same, back (near BL/BR headers). |
| D1 | LED, 0805 | `LED` | Lights when the servo rail is on. |
| R3 | **1k**, 0805 | `R` | Current limit for D1. |
| D2 | LED, 0805 | `LED` | Lights when the Pi rail is on. |
| R4 | **1k**, 0805 | `R` | Current limit for D2. |

### Section 4: Pi, servo driver, servos, extras

| Ref | Part | KiCad symbol | What it does |
|---|---|---|---|
| J2 | 2×20 female header, 2.54 mm | `Conn_02x20_Odd_Even` | The Pi Zero 2 W plugs in here. Gives it 5 V and connects I2C (pins 3/5) and GPIO17 (pin 11). |
| U4 | PCA9685PW (TSSOP-28) | search `PCA9685` | Servo driver. Takes I2C commands from the Pi and makes 16 PWM signals (we use 12). Address **0x40**, sits under the Pi. |
| C5 | **100nF**, 0805 | `C` | Decoupling for U4, right next to its VDD pin. |
| C6 | **10µF**, 0805 | `C` | Extra smoothing for U4's 3.3 V supply. |
| R5 | **10k**, 0805 | `R` | Pulls U4's OE pin high, so all servo outputs stay **off** at boot until the code pulls GPIO17 low. |
| JP1 | Solder jumper (2 pads) | `SolderJumper_2_Open` | Bridge it to tie OE to GND and skip the GPIO17 feature. |
| R6–R17 | **220Ω** ×12, 0805 | `R` | One per servo signal. Protects U4 if a servo wire shorts. |
| R18, R19 | **4.7k** ×2, 0805, **DNP** | `R` | Spare I2C pull-ups. Not fitted: the Pi already has them. Pads are there just in case. |
| J15–J26 | 1×3 male header, 2.54 mm ×12 | `Conn_01x03` | Servo plugs: signal / 5 V / GND. Three per corner, labelled FL, FR, BL, BR + hip/mid/end. |
| J3 | JST-SH 4-pin (Qwiic / STEMMA QT) | `Conn_01x04` | Spare I2C port for an IMU later. GND, 3.3 V, SDA, SCL. |
| TP1–TP5 | Test points | `TestPoint` | Probe spots: VBAT, 5V_SERVO, 5V_PI, 3V3, GND. |
| H1–H4 | M3 mounting holes | `MountingHole` | Screw the board to the body. Corners, 4 mm in. |
| H5–H8 | M2.5 mounting holes | `MountingHole` | Pi standoffs, 58 × 23 mm apart. |

### Servo channel map

Matches `SERVO_CHANNELS` in `controller/ik_controller.py`:

| Header | Channel | Leg | Joint |
|---|---|---|---|
| J15, J16, J17 | 0, 1, 2 | FR | hip, mid, end |
| J18, J19, J20 | 3, 4, 5 | BR | hip, mid, end |
| J21, J22, J23 | 6, 7, 8 | FL | hip, mid, end |
| J24, J25, J26 | 9, 10, 11 | BL | hip, mid, end |

### Net names

Use these labels in the schematic so everything lines up:

| Net | What |
|---|---|
| `VBAT` | Battery after the fuse and MOSFET (6.6–8.4 V) |
| `VBAT_SENSE` | After the shunt, feeds the bucks |
| `+5V_SERVO` | Servo rail |
| `+5V_PI` | Pi rail |
| `+3V3` | From the Pi's pin 1, for U1, U4, J3 |
| `SDA`, `SCL` | I2C |
| `SERVO_OE` | GPIO17 → U4 OE |
| `GND` | Ground (everything) |

---

## Footprints

### What a footprint is

The schematic says *what connects to what*. A **footprint** says *what the part physically looks like on the board*: the copper pads it gets soldered to, their size and spacing, and its outline. Each schematic symbol gets one footprint. The same 10k resistor symbol could be a tiny 0402 chip or a big through-hole resistor; the footprint is where you choose.

Get it wrong and the real part won't fit the pads. That's the #1 beginner mistake, so check every footprint against the part you'll actually buy.

Assign them in **Tools → Assign Footprints**. Select parts in the middle column (Ctrl-click for several), find the footprint on the right, double-click.

### How to read a footprint name

KiCad names are `Library:Footprint`, and the name packs in the dimensions. Taking them apart:

| Bit | Example | Meaning |
|---|---|---|
| Library | `Resistor_SMD:` | Which collection it's in. `_SMD` = surface mount, `_THT` = through-hole. |
| Size code | `0805` | Imperial size of a chip part: 0.08 × 0.05 inch. Bigger number = bigger part. 0402 is tiny, 0805 is easy to hand-solder, 2512 is big (handles more power). |
| Metric code | `2012Metric` | The same size in metric: 2.0 × 1.2 mm. |
| `P` | `P2.54mm` | **Pitch**: distance between pin centres. 2.54 mm (0.1") is the standard header spacing. 0.65 mm is fine-pitch and harder to solder. |
| `D` | `D10.0mm` | **Diameter** of a round part, like an electrolytic capacitor. |
| Rows × pins | `1x03`, `2x20` | Pin layout. 1 row of 3, or 2 rows of 20. |
| `Vertical` / `Horizontal` | | Which way the connector points. Vertical sticks straight up; horizontal (right-angle) points sideways off the board edge. |
| `PinHeader` / `PinSocket` | | Male pins / female sockets. |

### Package types used here

| Package | What it looks like | Used for |
|---|---|---|
| **0805** | Small rectangular chip, two pads | Most resistors, small capacitors, LEDs |
| **2512** | Big rectangular chip | R2 shunt: all battery current flows through it, so it needs to handle the heat |
| **CP_Radial** | Cylinder standing up, two legs through holes | Electrolytic capacitors. `CP` = polarized. |
| **SOT-23-8** | Tiny 8-pin chip | U1 INA219 |
| **TSSOP-28** | Thin 28-pin chip, 0.65 mm pitch | U4 PCA9685. Fine pitch: best assembled by the factory. |
| **TO-252 (DPAK)** | 3 pins with a big metal tab | Q1 MOSFET. The tab is a heatsink soldered to the board. |
| **PinHeader / PinSocket** | Standard 2.54 mm pins | Servo plugs, Pi header, buck module placeholders |
| **JST-SH** | Tiny 1 mm pitch latching connector | J3 Qwiic port |
| **SolderJumper** | Two pads close together | JP1. Bridge with solder to connect. |
| **TestPoint_Pad** | A bare round pad | TP1–TP5, for multimeter probes |

### Footprint for every part

| Parts | Footprint | Why |
|---|---|---|
| R1, R3–R19 | `Resistor_SMD:R_0805_2012Metric` | Standard small resistor, easy to hand-solder |
| C1, C5, C6 | `Capacitor_SMD:C_0805_2012Metric` | Same size, for small capacitors |
| D1, D2 | `LED_SMD:LED_0805_2012Metric` | Small indicator LEDs |
| R2 | `Resistor_SMD:R_2512_6332Metric` | Big, carries all the battery current |
| C2 | `Capacitor_THT:CP_Radial_D6.3mm_P2.50mm` | 100 µF electrolytic, 6.3 mm wide |
| C3, C4 | `Capacitor_THT:CP_Radial_D10.0mm_P5.00mm` | 1000 µF electrolytic, 10 mm wide |
| Q1 | `Package_TO_SOT_SMD:TO-252-2` | DPAK MOSFET (AOD4185). Pins 1 = gate, 2 = drain, 3 = source, same as the symbol. |
| U1 | `Package_TO_SOT_SMD:SOT-23-8` | INA219AxDCN package |
| U4 | `Package_SO:TSSOP-28_4.4x9.7mm_P0.65mm` | PCA9685PW package |
| J1 | XT30 **PW** (horizontal) from `Connector_AMASS` | Battery plug, points out the back edge |
| F1 | Mini blade fuse holder (search `Blade_Mini`) | Takes standard car-style mini fuses |
| J2 | `Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical` | Female socket, the Pi plugs in from above |
| J15–J26 | `Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical` | Male pins, servo plugs push on |
| J3 | JST-SH `SM04B` Horizontal | Qwiic port |
| JP1 | `SolderJumper-2` Open | Open by default |
| TP1–TP5 | `TestPoint:TestPoint_Pad_D1.5mm` | 1.5 mm probe pads |
| U2, U3 | `PinHeader_1x03_P2.54mm_Vertical` **(placeholder)** | Replaced with exact module footprints once the modules are chosen |

---

## Board size and layout

- **99 × 79 mm** (100 × 80 max, minus 0.5 mm each side for tolerance). Under 100 × 100 is the cheapest tier at JLCPCB / PCBWay.
- Mounted **on top** of the robot, battery underneath.
- **Front is along the 99 mm length.**

```
                    FRONT
   ┌─────────────── 79 mm ───────────────┐
   │ ◯ [FL servos ×3]   [FR servos ×3] ◯ │
   │   (C3)                              │
   │                    ┌─ camera end ─┐ │
   │  [U2 SERVO BUCK]   │              │ │
   │                    │  Pi Zero 2 W │ │
   │  [U3 PI BUCK]      │   65 × 30    │ │ 99 mm
   │                    │              │ │
   │  U1  LEDs          │ U4 + R6–R17  │ │
   │                    │ underneath   │ │
   │  Q1  F1            │              │ │
   │                    └── SD end ────┘ │
   │   (C4)                 J3           │
   │ ◯ [BL servos ×3]   [BR servos ×3] ◯ │
   └──────────── J1 XT30 (battery) ──────┘
                    BACK
```

- Power runs up the left side in battery order, away from the Pi and I2C.
- Pi lengthwise, camera connector forward (for CV later), SD card at the back.
- Only flat parts under the Pi (it sits ~11 mm up on its header). Bucks and big caps go elsewhere.

---

## Gotchas

- **Two chips at 0x40.** INA219 A0 → 3.3 V. Already handled above, but it's the classic mistake.
- **Don't run LiPos flat.** Watch the INA219 voltage. Stop at ~6.8 V under load.
- **Wire gauge:** battery leads 18 AWG or thicker.
- **Measure the body before routing.** Re-routing is easy; reprinting a body because a connector hits the shell is annoying.
- **Check the footprint against the real part** (print the PCB 1:1 on paper and lay the parts on it). Wrong footprint is the #1 beginner respin.
- **v1 will have a mistake.** That's normal. Bodge wires exist. Note it, fix it in v2.
