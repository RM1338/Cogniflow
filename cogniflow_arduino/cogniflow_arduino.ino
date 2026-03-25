/*
 * cogniflow_arduino.ino
 * ---------------------
 * Cogniflow Arduino Actuator Controller
 *
 * Receives JSON state commands from the laptop over USB Serial
 * and drives an RGB LED strip + fan via two L298N motor drivers.
 *
 * Protocol:
 *   Laptop → Arduino:  {"state":"FOCUS","fan":0,"r":255,"g":255,"b":240}\n
 *   Arduino → Laptop:  "READY\n" on boot, "ACK:<STATE>\n" on each command
 *
 * Dependencies:
 *   - ArduinoJson (install via Library Manager)
 */
#include <ArduinoJson.h>

// --- L298N #1 (Red + Green) ---
#define ENA  9
#define IN1  4
#define IN2  2    // ← MOVED from pin 5 to free it for fan ENB
#define ENB  10
#define IN3  6
#define IN4  7

// --- L298N #2 Channel A (Blue LED) ---
#define ENA2   3
#define IN1_2  11
#define IN2_2  12

// --- L298N #2 Channel B (Fan) ---
#define ENB2   5
#define IN3_2  8
#define IN4_2  13

// ── INPUT BUFFER ─────────────────────────────────────────────────────────────
String inputBuffer = "";

// ── LED CONTROLS ─────────────────────────────────────────────────────────────
void setRed(int brightness) {
  analogWrite(ENA, constrain(brightness, 0, 255));
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
}

void setGreen(int brightness) {
  analogWrite(ENB, constrain(brightness, 0, 255));
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
}

void setBlue(int brightness) {
  analogWrite(ENA2, constrain(brightness, 0, 255));
  digitalWrite(IN1_2, LOW);
  digitalWrite(IN2_2, HIGH);
}

void setAllLEDs(int r, int g, int b) {
  setRed(r);
  setGreen(g);
  setBlue(b);
}

void allOff() {
  analogWrite(ENA,  0);
  analogWrite(ENB,  0);
  analogWrite(ENA2, 0);
}

// ── FAN CONTROLS ─────────────────────────────────────────────────────────────
void setFan(int speed) {
  // speed: 0–255
  analogWrite(ENB2, constrain(speed, 0, 255));
}

// ── SETUP ────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  // L298N #1 — Red + Green
  pinMode(ENA, OUTPUT); pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(ENB, OUTPUT); pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);

  // L298N #2 Channel A — Blue LED
  pinMode(ENA2,  OUTPUT); pinMode(IN1_2, OUTPUT); pinMode(IN2_2, OUTPUT);

  // L298N #2 Channel B — Fan
  pinMode(ENB2,  OUTPUT); pinMode(IN3_2, OUTPUT); pinMode(IN4_2, OUTPUT);
  digitalWrite(IN3_2, HIGH);  // Fan direction set once, never changes
  digitalWrite(IN4_2, LOW);

  // Start everything off
  allOff();
  setFan(0);

  // Boot indicator — dim blue
  setAllLEDs(0, 30, 60);
  delay(500);

  Serial.println("READY");
}

// ── MAIN LOOP ────────────────────────────────────────────────────────────────
void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      processCommand(inputBuffer);
      inputBuffer = "";
    } else {
      inputBuffer += c;
    }
  }
}

// ── COMMAND PROCESSOR ────────────────────────────────────────────────────────
void processCommand(String json) {
  json.trim();
  if (json.length() == 0) return;

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, json);
  if (error) {
    Serial.print("ERR:JSON_PARSE:");
    Serial.println(error.c_str());
    return;
  }

  const char* state = doc["state"] | "UNKNOWN";
  int r             = doc["r"]     | 0;
  int g             = doc["g"]     | 0;
  int b             = doc["b"]     | 0;
  int fan           = doc["fan"]   | 0;  // 0–255

  // Apply LEDs
  if (r == 0 && g == 0 && b == 0) {
    allOff();
  } else {
    setAllLEDs(r, g, b);
  }

  // Apply fan
  setFan(fan);

  // ACK back to laptop
  Serial.print("ACK:");
  Serial.println(state);
}