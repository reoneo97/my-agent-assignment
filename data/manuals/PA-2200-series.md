# PA-2200 Series — High Pressure Alarm Procedures

**Equipment:** DieAttach Line 2 / Unit 4  
**Alarm Codes:** PA-2201, PA-2202  
**Severity:** Medium (PA-2201), High (PA-2202)  
**Category:** Mechanical  
**Expected Disposition:** Self-resolve (PA-2201), Either (PA-2202)

---

## Alarm PA-2201 — High Pressure Alarm (Standard)

**Description:** Pressure on the die-attach bonding head has exceeded the upper threshold
(>120 PSI) during a standard bonding cycle. Typically caused by a blocked pressure
relief port or transient spike.

**Complexity:** Low

### Procedure PROC-PA-2201-RESET — High Pressure Reset

**Required Skills:** basic_alarm_response, pressure_system_maintenance  
**Available Modalities:** VISUAL, TEXT

#### Steps

1. Check the pressure gauge on the Line 2 display panel. Confirm reading exceeds 120 PSI.
2. If the gauge confirms >120 PSI, locate manual relief valve V-4 on the left side panel
   and open it one quarter turn.
3. Wait 30 seconds for pressure to normalise. The gauge should return to the 80–100 PSI
   operating range.
4. Reset the alarm using the HMI panel: navigate to Alarms → Active → PA-2201 → Acknowledge.
5. Resume the bonding cycle and monitor for 5 minutes.
6. If the alarm recurs within 10 minutes, escalate to the maintenance supervisor —
   do not attempt a second manual reset without maintenance sign-off.

---

## Alarm PA-2202 — High Pressure Alarm (Critical Threshold)

**Description:** Pressure has exceeded the critical threshold (>150 PSI).
Indicates a potential seal failure or stuck relief valve.

**Complexity:** Medium  
**Severity:** High  
**Expected Disposition:** Either (attempt reset once; escalate if unsuccessful)

### Procedure PROC-PA-2201-RESET (same reset procedure applies for initial attempt)

If reset fails within 5 minutes, escalate immediately to maintenance.
Do not operate Line 2 until maintenance has cleared the fault.

---

## Safety Notes

- Never bypass the pressure relief valve assembly.
- If you smell burning or hear unusual noise during a pressure alarm, evacuate the
  immediate area and call maintenance immediately.
- Escalation is always the correct action if you are unsure. There is no penalty for
  getting help early.
