# Quadruped PCB

A custom board to replace the rats' nest of wires between the battery, the Pi, the PCA9685 breakout and the 12 servos. Designed in KiCad.

**Status:** planning. Nothing drawn yet. This is the plan and the "what is a PCB" crash course.

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
- **Reverse-polarity protection:** a P-channel MOSFET wired as an "ideal diode". If you plug the battery in backwards, the MOSFET stays off and nothing gets hurt. A normal diode would also work but wastes ~2.5 W as heat at 5 A; the MOSFET wastes a few tens of mW. Pick one rated for **−20 V or −30 V, >10 A, low R<sub>DS(on)</sub>** (e.g. AO4407A or similar, SOIC-8). Gate goes to GND through a ~10 kΩ resistor. Google "P-channel MOSFET reverse polarity protection", it's a 2-part circuit.
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
| Servo 5 V | Pololu **D24V50F5** (5 V, 5 A) or similar | Add a 1000–2200 µF, 16 V low-ESR electrolytic cap on its output, right by the servo headers. |
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

## Rough BOM

| Qty | Part | Notes |
|---|---|---|
| 1 | XT30 male, PCB mount | Battery in |
| 1 | Mini blade fuse holder + 7.5 A fuse | |
| 1 | P-MOSFET, −20/−30 V, >10 A, SOIC-8 | Reverse polarity |
| 1 | INA219 + 0.01 Ω 2512 shunt | Battery monitor, address 0x41 |
| 1 | 5 V / 5 A buck module | Servo rail |
| 1 | 5 V / 2.5 A buck module | Pi rail |
| 1 | 1000–2200 µF 16 V low-ESR electrolytic | Servo rail bulk cap |
| 1 | PCA9685PW (TSSOP-28) | Servo driver |
| 12 | 220 Ω 0805 | Servo signal series |
| ~4 | 10 kΩ 0805 | OE pull-up, MOSFET gate, etc |
| 2 | 4.7 kΩ 0805 (DNP) | Optional I2C pull-ups |
| ~6 | 100 nF 0805 | Decoupling, one per chip + spares |
| ~3 | 10 µF 0805 | Bulk near chips |
| 12 | 1×3 2.54 mm male header | Servos |
| 1 | 2×20 2.54 mm female header | Pi |
| 1 | JST-SH 4-pin (Qwiic) | Spare I2C |
| 2–3 | LED + 1 kΩ | Power indicators |
| 4+ | M2.5 / M3 mounting holes | |

---

## Gotchas

- **Two chips at 0x40.** INA219 A0 → 3.3 V. Already handled above, but it's the classic mistake.
- **Don't run LiPos flat.** Watch the INA219 voltage. Stop at ~6.8 V under load.
- **Wire gauge:** battery leads 18 AWG or thicker.
- **Measure the body before routing.** Re-routing is easy; reprinting a body because a connector hits the shell is annoying.
- **Check the footprint against the real part** (print the PCB 1:1 on paper and lay the parts on it). Wrong footprint is the #1 beginner respin.
- **v1 will have a mistake.** That's normal. Bodge wires exist. Note it, fix it in v2.
