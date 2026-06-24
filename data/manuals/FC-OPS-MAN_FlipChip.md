# Flip Chip System — Operator Reference Manual

**Document:** FC-OPS-MAN Rev. 2.0
**Applies to:** FlipChip platform machines (FC-series, Lines 1–3)
**Audience:** Certified shopfloor operators
**Last reviewed:** 2024-10

---

## 1. Overview

The Flip Chip system places die face-down onto the substrate and forms
interconnects via reflowed solder bumps, governed by a process recipe. This
manual covers operator-level response for the recipe and alignment-sensor
subsystems. Recipe parameter issues are routinely operator-resolvable. Sensor
alignment faults use operator judgement.

Operators require **basic_alarm_response** certification. Recipe work requires
**recipe_management**; alignment-sensor diagnostics require
**sensor_diagnostics** and, for hands-on alignment, **flip_chip_alignment**.

---

## 2. Alarm Index (Flip Chip platform)

| Code | Subsystem | Severity | Complexity | Category | Expected disposition |
|---|---|---|---|---|---|
| RC-3301 | Recipe | Low | Medium | Recipe | Operator self-resolve |
| SN-0710 | Alignment sensor | Medium | Medium | Sensor | Either (judgement) |

> **Note.** SN-0710 is an alignment-sensor alarm. Operators may attempt the
> diagnostic reset below; if alignment confidence does not recover, escalate to
> the alignment specialist rather than running repeated reflow cycles.

---

## 3. Procedures

### 3.1 PROC-RC-3301-RELOAD — Recipe Parameter Reload

**Resolves:** RC-3301
**Requires skills:** recipe_management
**Available formats:** text checklist
**Expected disposition:** operator self-resolve

A RC-3301 alarm indicates the active process recipe has drifted from or failed to
load its expected parameter set. This is routine and operator-resolvable.

**Steps**
1. Open the recipe manager on the FC HMI and confirm the active recipe ID matches
   the run sheet.
2. If the ID is wrong or parameters are flagged, reload the correct recipe from
   the validated recipe library.
3. Confirm all parameters show "in-spec" before resuming the run.
4. Log the reload in the shift report.

### 3.2 PROC-SN-0710-ALIGN — Alignment Sensor Diagnostic Reset

**Resolves:** SN-0710
**Requires skills:** sensor_diagnostics, flip_chip_alignment
**Available formats:** annotated diagram (visual), text checklist
**Expected disposition:** either — escalate if alignment confidence does not recover

> *This procedure is referenced in the alarm index but is not yet in the
> structured procedure database — a good candidate for extraction to add.*

An SN-0710 alarm indicates the alignment sensor's confidence score has fallen
below threshold during placement.

**Steps**
1. Pause the run at the current unit; do not advance to reflow.
2. Open the alignment diagnostics screen and run the fiducial re-acquisition
   routine.
3. Check that the alignment confidence score returns above 0.90.
4. If confidence recovers, resume. If it does not recover after two attempts,
   escalate to the alignment specialist — do not run repeated reflow cycles, as
   misaligned reflow causes scrap.

---

## 4. Escalation Notes

- Recipe alarms that recur immediately after a correct reload may indicate a
  corrupted recipe-library entry; escalate to process engineering.
- Repeated SN-0710 events on the same machine suggest sensor drift or a mechanical
  alignment-stage issue; escalate rather than continuing to re-acquire.
