# Wire Bond Press — Operator Reference Manual

**Document:** WB-OPS-MAN Rev. 3.1
**Applies to:** WireBond press machines (WB-series, Presses A–E)
**Audience:** Certified shopfloor operators
**Last reviewed:** 2024-09

---

## 1. Overview

The Wire Bond press forms electrical interconnects between die and lead frame
using ultrasonic bonding under hydraulic clamp pressure. This manual covers
operator-level response for the hydraulic subsystem. **Hydraulic faults on this
platform are safety-significant: operators must not attempt repair.** The
operator's role is to isolate the press and escalate.

Operators require **basic_alarm_response** certification to acknowledge alarms.
The **hydraulics** certification is required to perform any hands-on hydraulic
work — but note that even certified operators do not self-resolve HY-series
faults; those are reserved for the maintenance specialist.

---

## 2. Alarm Index (Wire Bond platform)

| Code | Subsystem | Severity | Complexity | Category | Expected disposition |
|---|---|---|---|---|---|
| HY-0042 | Hydraulics | High | High | Mechanical | **Escalate (mandatory)** |
| HY-0043 | Hydraulics | Medium | High | Mechanical | **Escalate (mandatory)** |

> **Important.** Both HY-series alarms are mandatory-escalation. Attempting to
> reset or clear a hydraulic fault without specialist sign-off is a safety
> violation, even when the press appears to operate normally afterward.

HY-0042 and HY-0043 are related faults in the same hydraulic subsystem and follow
the same inspect-and-escalate procedure; the difference is severity, not handling.

---

## 3. Procedures

### 3.1 PROC-HY-0042-INSPECT — Hydraulic Fault Inspection and Escalation

**Resolves:** HY-0042, HY-0043
**Requires skills:** hydraulics
**Available formats:** text checklist
**Expected disposition:** mandatory escalation — operator isolates and hands off

A HY-series alarm indicates a hydraulic clamp-pressure fault. The operator's job
is containment and handoff, not repair.

**Steps**
1. **Do not attempt a reset.** Isolate the press hydraulics immediately.
2. Check the hydraulic fluid level in the reservoir sight glass and note it for
   the handoff.
3. Call the maintenance supervisor — this fault requires specialist sign-off
   before the press returns to service.

No visual job aid is published for this procedure; it is intentionally text-only
to discourage operators from treating it as a routine self-resolve task.

---

## 4. Escalation Notes

- A press that resumes normal operation after a HY-series alarm has **not** been
  cleared — the underlying fault is unresolved until maintenance signs off.
- If an operator observes a colleague resetting a hydraulic alarm without
  escalation, this should be reported; it is a recurring safety concern on this
  platform.
- Repeated HY-0043 (medium) events can precede a HY-0042 (high) failure; treat a
  pattern of HY-0043 as an early warning and escalate promptly.
