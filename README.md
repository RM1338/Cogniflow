# Cogniflow — Cognitive Load Adaptive Physical Environment

## File Structure

```
Cogniflow/
├── config.py              ← All constants. Edit this first.
│
├── bandClassifier.py      ← EEG board, band power, state classifier
├── musicPlayer.py         ← Adaptive music playback (pygame)
├── socketClient.py        ← UDP sender: laptop → RPi
├── laptopBrain.py         ← LAPTOP entry point
│
├── hardwareController.py  ← Fan, LED, OLED drivers
├── socketServer.py        ← UDP receiver on RPi
├── rpiActuators.py        ← RPi entry point
│
├── testBands.py           ← Verify EEG pipeline (run first)
└── testHardware.py        ← Verify RPi actuators (run first)
```

---

## Step 0 — Configure First

Open `config.py`. Change one line:
```python
RPI_IP: str = "192.168.1.x"   # ← your RPi's actual IP
```
Find RPi IP with: `hostname -I` (run on RPi)

---

## Step 1 — Install Dependencies

**On laptop (victus):**
```bash
pip install muselsl brainflow scipy numpy pygame
```

**On Raspberry Pi:**
```bash
pip install rpi_ws281x gpiozero luma.oled pillow
sudo apt-get install python3-smbus i2c-tools -y
sudo raspi-config   # Interface Options → I2C → Enable → Reboot
```

---

## Step 2 — Test EEG Pipeline (Laptop)

```bash
# Terminal 1
muselsl stream

# Terminal 2
python3 testBands.py
```

Expected output — three numbers updating every 0.5s:
```
θ:  0.00231   α:  0.00412   β:  0.00189
```
Close your eyes → α rises. Do mental math → β rises.

---

## Step 3 — Test Hardware (RPi)

```bash
sudo python3 testHardware.py
```
Fan spins 3s. LEDs cycle 4 colours. OLED shows each state label.

---

## Step 4 — Run the Full System

```bash
# RPi — run first
sudo python3 rpiActuators.py

# Laptop Terminal 1
muselsl stream

# Laptop Terminal 2
python3 laptopBrain.py
```

---

## Music Files

Place these MP3s in the same directory as `laptopBrain.py`:
- `focusLofi.mp3`
- `drowsyUpbeat.mp3`
- `stressedCalm.mp3`

Download free tracks:
```bash
yt-dlp -x --audio-format mp3 -o "focusLofi.mp3" [YouTube URL]
```

---

## Expected Terminal Output (Laptop)

```
  ╔═══════════════════════════════════╗
  ║          Cogniflow  v1.0          ║
  ╚═══════════════════════════════════╝

  [ CALIBRATING ]  Sit still, eyes open, breathe normally.
  This takes 60 seconds...

  [ BASELINE SET ]  θ=0.0023  α=0.0041  β=0.0019

  [ RUNNING ]  Monitoring cognitive state...

  🔵  STATE → RELAXED     |  θ: 0.9210   α: 1.3120   β: 0.8810
  🟢  STATE → FOCUS       |  θ: 0.8120   α: 0.6310   β: 1.3410
  🔴  STATE → STRESSED    |  θ: 0.9340   α: 0.7120   β: 1.9230
```