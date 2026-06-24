# Die Attach System — Operator Reference Manual

**Document:** DA-OPS-MAN Rev. 4.2
**Applies to:** DieAttach platform machines (DA-series, Lines 1–3 and Unit 4)
**Audience:** Certified shopfloor operators
**Last reviewed:** 2024-11

---

## 1. Overview

The Die Attach system bonds singulated die to the substrate using a dispensed
adhesive and a pick-and-place head. This manual covers operator-level alarm
response for the pressure, flow-sensor, and dispense subsystems. Faults
requiring tool disassembly or specialist sign-off are out of scope and must be
escalated per the disposition noted on each alarm.

Operators must hold the **basic_alarm_response** certification before clearing
any alarm on this platform. Pressure-system alarms additionally require
**pressure_system_maintenance**; flow-sensor calibration requires
**flow_calibration** and **sensor_diagnostics**.

---

## 2. Alarm Index (Die Attach platform)

| Code | Subsystem | Severity | Complexity | Category | Expected disposition |
|---|---|---|---|---|---|
| PA-2201 | Pressure | Medium | Low | Mechanical | Operator self-resolve |
| PA-2202 | Pressure | High | Medium | Mechanical | Either (judgement) |
| FL-1105 | Flow sensor | Medium | Medium | Sensor | Either (judgement) |
| FL-1106 | Flow sensor | Low | Low | Sensor | Operator self-resolve |

> **Disposition key.** *Self-resolve* = operator is expected to clear the alarm
> using the procedure below. *Escalate* = operator must hand off to maintenance,
> not attempt a fix. *Either* = operator judgement; escalate if the resolution
> step fails or the fault recurs.

Pressure alarms PA-2201 and PA-2202 are part of the same PA-2200 pressure series
and share a common reset procedure; an operator comfortable with one is generally
comfortable with the other. Flow-sensor alarms FL-1105 and FL-1106 are likewise
related and share the FL-1100 calibration routine.

---

## 3. Procedures

### 3.1 PROC-PA-2201-RESET — High Pressure Alarm Reset (PA-2200 series)

**Resolves:** PA-2201, PA-2202
**Requires skills:** basic_alarm_response, pressure_system_maintenance
**Available formats:** annotated diagram (visual), text checklist

A PA-2200-series alarm indicates line pressure has exceeded the safe operating
threshold. For PA-2201 (medium severity) the operator is expected to reset the
alarm directly. For PA-2202 (high severity), use judgement: if venting does not
bring pressure into range on the first attempt, escalate rather than retry.

**Steps**
1. Check the pressure gauge on the Line 2 display panel.
2. If the gauge reads above 120 PSI, vent the line using manual relief valve V-4.
3. Wait 30 seconds, then reset the alarm from the HMI panel.
4. If the alarm recurs within 10 minutes, escalate to maintenance — do not keep
   resetting.

A labelled diagram of valve V-4 and the HMI reset sequence is available on the
panel help screen and in the visual job aid.

### 3.2 PROC-FL-1105-CALIB — Flow Sensor Calibration (FL-1100 series)

**Resolves:** FL-1105, FL-1106
**Requires skills:** flow_calibration, sensor_diagnostics
**Available formats:** annotated diagram (visual), instructional video

A FL-1100-series alarm indicates the dispense flow reading has drifted outside
the nominal band. FL-1106 (low severity) is routine and operator-resolvable.
FL-1105 (medium severity) is also operator-resolvable but uses judgement: if
auto-calibration does not restore nominal flow, escalate for sensor replacement.

**Steps**
1. Navigate to the Unit 4 sensor diagnostics screen.
2. Run the auto-calibration sequence (takes approximately 2 minutes).
3. Verify the flow reading returns to nominal (4.5–5.5 L/min).
4. Log the calibration event in the shift report.

A short instructional video covering the calibration screen is linked from the
diagnostics page.

---

## 4. Escalation Notes

- Never bypass a pressure interlock to silence a PA-2200 alarm.
- Repeated PA-2202 occurrences on the same machine within a shift indicate a
  developing mechanical fault — escalate even if each individual reset succeeds.
- Flow-sensor drift that returns immediately after calibration suggests sensor
  failure rather than calibration error; escalate for replacement.
